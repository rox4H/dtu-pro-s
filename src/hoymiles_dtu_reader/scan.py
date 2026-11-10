"""Read-only register scanner for meters on the DTU bus.

Nothing here writes. It exists so a new meter model can be checked against
real hardware before a decoder is trusted: it prints raw registers plus both
float32 word orders so the right layout can be read off the output.
"""
from __future__ import annotations

import math
import struct
from collections.abc import Callable, Iterable

from hoymiles_dtu_reader.errors import ModbusError, ModbusExceptionResponse

DEFAULT_RANGES = ((0x2000, 50), (0x4000, 20), (0x101E, 12))
CHUNK = 50


def parse_range(text: str) -> tuple[int, int]:
    start, _, count = text.partition(":")
    start_i = int(start, 0)
    count_i = int(count, 0) if count else 20
    if not 0 <= start_i <= 0xFFFF or not 1 <= count_i <= 250:
        raise ValueError(f"invalid range '{text}' (use START:COUNT, e.g. 0x2000:50)")
    return start_i, count_i


def parse_slaves(text: str) -> list[int]:
    slaves: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            low, _, high = part.partition("-")
            slaves.extend(range(int(low), int(high) + 1))
        else:
            slaves.append(int(part))
    if not slaves or any(not 1 <= item <= 247 for item in slaves):
        raise ValueError("slaves must be within 1..247")
    return slaves


def _float(high: int, low: int, high_first: bool) -> float:
    raw = (high << 16) | low if high_first else (low << 16) | high
    value = struct.unpack(">f", raw.to_bytes(4, "big"))[0]
    return value


def _fmt(value: float) -> str:
    if math.isnan(value) or math.isinf(value) or (value != 0 and abs(value) < 1e-6) or abs(value) > 1e9:
        return "-"
    return f"{value:.4g}"


def find_meters(
    modbus,
    slaves: Iterable[int],
    out: Callable[[str], None] = print,
    probe_address: int = 0x2000,
) -> list[int]:
    """List slave ids that answer a 2-register read. Says nothing about model."""
    timeout, retries = modbus.timeout, modbus.retries
    modbus.timeout, modbus.retries = min(float(timeout), 1.0), 0
    found: list[int] = []
    try:
        for slave in slaves:
            try:
                registers = modbus.read_holding_registers(probe_address, 2, slave)
            except ModbusExceptionResponse as exc:
                out(f"slave {slave:>3}: answers (exception code {exc.code}) -> a device is there")
                found.append(slave)
            except ModbusError:
                continue
            else:
                out(f"slave {slave:>3}: answers, regs {registers[0]:#06x} {registers[1]:#06x}")
                found.append(slave)
    finally:
        modbus.timeout, modbus.retries = timeout, retries
    if not found:
        out("no slave answered")
    return found


def dump_registers(
    modbus,
    slave: int,
    ranges: Iterable[tuple[int, int]] = DEFAULT_RANGES,
    out: Callable[[str], None] = print,
) -> None:
    timeout, retries = modbus.timeout, modbus.retries
    modbus.timeout, modbus.retries = min(float(timeout), 2.0), 0
    try:
        for start, count in ranges:
            out(f"\n# slave {slave}  {start:#06x} .. {start + count - 1:#06x}")
            out("# addr    raw        u16 pair        float32 (hi-first | lo-first)")
            done = 0
            while done < count:
                size = min(CHUNK, count - done)
                address = start + done
                try:
                    registers = modbus.read_holding_registers(address, size, slave)
                except ModbusExceptionResponse as exc:
                    out(f"{address:#06x}  not readable (exception code {exc.code})")
                    done += size
                    continue
                except ModbusError as exc:
                    out(f"{address:#06x}  error: {exc}")
                    done += size
                    continue
                for index in range(0, len(registers) - 1, 2):
                    first, second = registers[index], registers[index + 1]
                    out(
                        f"{address + index:#06x}  {first:#06x} {second:#06x}  "
                        f"{first:>5} {second:>5}   "
                        f"{_fmt(_float(first, second, True)):>10} | {_fmt(_float(first, second, False)):>10}"
                    )
                done += size
    finally:
        modbus.timeout, modbus.retries = timeout, retries
