from __future__ import annotations

import argparse
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from hoymiles_dtu_reader import __version__
from hoymiles_dtu_reader.config import Settings, load_env_file
from hoymiles_dtu_reader.devices.hoymiles import HoymilesDTU
from hoymiles_dtu_reader.factory import build_accessories
from hoymiles_dtu_reader.local_api import create_server
from hoymiles_dtu_reader.poller import poll_once
from hoymiles_dtu_reader.scan import DEFAULT_RANGES, dump_registers, find_meters, parse_range, parse_slaves
from hoymiles_dtu_reader.state import StateStore
from hoymiles_dtu_reader.transport.modbus_tcp import ModbusTCP

log = logging.getLogger("hoymiles_dtu_reader")


def setup_logging(log_dir: str) -> None:
    logger = logging.getLogger("hoymiles_dtu_reader")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)
    try:
        path = Path(log_dir)
        path.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path / "hoymiles-dtu-reader.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as exc:
        logger.warning("File logging disabled (%s): %s", log_dir, exc)


def _fmt_w(value: float | None) -> str:
    return "      -" if value is None else f"{value:7.0f}"


def run(settings: Settings | None = None) -> None:
    settings = settings or Settings.from_env()
    setup_logging(settings.log_dir)
    accessories = build_accessories(settings)

    log.info("Hoymiles DTU Reader %s", __version__)
    log.info(
        "DTU %s:%s (slave %s, type %s)",
        settings.dtu_ip,
        settings.dtu_port,
        settings.dtu_slave_id,
        settings.hoymiles_type,
    )
    log.info("Accessories: %s", ", ".join(settings.accessories) or "none")

    modbus = ModbusTCP(
        settings.dtu_ip,
        settings.dtu_port,
        settings.modbus_timeout,
        settings.modbus_retries,
    )
    hoymiles = HoymilesDTU(
        modbus,
        settings.dtu_slave_id,
        settings.hoymiles_type,
        settings.max_microinverters,
    )
    store = StateStore()
    stop = threading.Event()

    def polling_loop() -> None:
        cycle = 0
        while not stop.is_set():
            cycle += 1
            try:
                state = poll_once(modbus, hoymiles, accessories, settings, cycle)
                store.set(state)
                summary = state["summary"]
                log.info(
                    "PV %s W | GRID %s W | LOAD %s W | INV %d | %.0f ms",
                    _fmt_w(summary["pv_power_w"]),
                    _fmt_w(summary["grid_power_w"]),
                    _fmt_w(summary["load_power_w"]),
                    len(state["microinverters"]),
                    state["diagnostics"]["poll_time_ms"],
                )
            except Exception as exc:
                log.error("Polling cycle failed: %s", exc)
                modbus.close()
                store.mark_error(exc)
            stop.wait(settings.poll_interval)

    polling_thread = threading.Thread(target=polling_loop, name="solar-polling", daemon=True)
    server = create_server(store, settings)
    polling_thread.start()
    log.info("Read-only API listening at http://%s:%s", settings.http_host, settings.http_port)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        stop.set()
        modbus.close()
        polling_thread.join(timeout=max(2.0, settings.modbus_timeout + 1.0))
        server.server_close()


def scan_meter(args: argparse.Namespace) -> None:
    settings = Settings.from_env()
    modbus = ModbusTCP(settings.dtu_ip, settings.dtu_port, settings.modbus_timeout, 0)
    try:
        if args.find:
            slaves = parse_slaves(args.slaves) if args.slaves else list(range(1, 31))
            slaves = [item for item in slaves if item != settings.dtu_slave_id]
            if not slaves:
                raise ValueError("no slave ids to scan")
            print(
                f"Searching slaves {slaves[0]}..{slaves[-1]} "
                f"through {settings.dtu_ip}:{settings.dtu_port}"
            )
            find_meters(modbus, slaves)
            return
        if args.slave is None:
            raise ValueError("use --find, or --slave N to dump registers")
        if args.slave == settings.dtu_slave_id:
            raise ValueError("that is the DTU slave id, not a meter")
        ranges = [parse_range(item) for item in args.range] or list(DEFAULT_RANGES)
        dump_registers(modbus, args.slave, ranges)
    finally:
        modbus.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hoymiles-dtu-reader",
        description="Read Hoymiles DTU data and expose a local JSON API.",
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("run", help="read the DTU and serve the local API")
    commands.add_parser("version", help="print the version")

    scan = commands.add_parser("scan-meter", help="find or inspect a CHINT meter (read-only)")
    scan.add_argument("--find", action="store_true", help="list slave ids that answer")
    scan.add_argument("--slaves", help="with --find: e.g. 1-30 or 2,3,22 (default 1-30)")
    scan.add_argument("--slave", type=int, help="dump registers of this slave id")
    scan.add_argument(
        "--range",
        action="append",
        default=[],
        metavar="START:COUNT",
        help="register range, e.g. 0x2000:50 (repeatable)",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "version":
        print(__version__)
        return

    try:
        load_env_file()
        if args.command == "scan-meter":
            scan_meter(args)
        else:
            run()
    except KeyboardInterrupt:
        log.info("Shutdown requested")
    except (OSError, ValueError) as exc:
        print(f"hoymiles-dtu-reader: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
