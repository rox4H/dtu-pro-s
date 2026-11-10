"""Shared fixtures: an in-process fake Modbus TCP DTU and register builders."""
from __future__ import annotations

import os
import socket
import socketserver
import struct
import threading

import pytest

from hoymiles_dtu_reader.errors import ModbusError


def microinverter_registers(
    serial: str = "112233445566",
    *,
    port: int = 1,
    pv_voltage_v: float = 32.5,
    pv_current_a: float = 8.2,
    grid_voltage_v: float = 231.4,
    grid_freq_hz: float = 50.01,
    pv_power_w: float = 266.5,
    today_wh: int = 1200,
    total_wh: int = 345678,
    temperature_c: float = 31.5,
    operating_status: int = 3,
    alarm_code: int = 0,
    alarm_count: int = 0,
    link_status: int = 1,
    hoymiles_type: str = "HM",
) -> list[int]:
    """Build the 20 holding registers (40 bytes) of one DTU-Pro microinverter slot."""
    current_scale = 100.0 if hoymiles_type == "HM" else 10.0
    data = bytearray(40)
    data[0] = 1
    data[1:7] = bytes.fromhex(serial)
    data[7] = port
    struct.pack_into(">H", data, 8, round(pv_voltage_v * 10))
    struct.pack_into(">H", data, 10, round(pv_current_a * current_scale))
    struct.pack_into(">H", data, 12, round(grid_voltage_v * 10))
    struct.pack_into(">H", data, 14, round(grid_freq_hz * 100))
    struct.pack_into(">H", data, 16, round(pv_power_w * 10))
    struct.pack_into(">H", data, 18, today_wh)
    struct.pack_into(">I", data, 20, total_wh)
    struct.pack_into(">h", data, 24, round(temperature_c * 10))
    struct.pack_into(">H", data, 26, operating_status)
    struct.pack_into(">H", data, 28, alarm_code)
    struct.pack_into(">H", data, 30, alarm_count)
    data[32] = link_status
    return list(struct.unpack(">20H", bytes(data)))


def float32_registers(value: float, *, low_word_first: bool = True) -> list[int]:
    """Encode a float32 across two 16-bit registers."""
    raw = struct.unpack(">I", struct.pack(">f", value))[0]
    high, low = raw >> 16, raw & 0xFFFF
    return [low, high] if low_word_first else [high, low]


def chint_block(
    *,
    voltage_v: float = 230.0,
    current_a: float = 5.0,
    total_power_w: float = -450.0,
    power_l1_w: float = -450.0,
    low_word_first: bool = True,
) -> list[int]:
    """Build the 50-register CHINT 0x2000 block with the values the reader decodes."""
    block = [0] * 50

    def put(address: int, value: float, scale: float) -> None:
        index = address - 0x2000
        block[index : index + 2] = float32_registers(value * scale, low_word_first=low_word_first)

    put(0x2006, voltage_v, 10.0)
    put(0x200C, current_a, 1000.0)
    put(0x2012, total_power_w, 10.0)
    put(0x2014, power_l1_w, 10.0)
    return block


class FakeModbus:
    """In-memory stand-in for ModbusTCP: {unit_id: {address: value}}."""

    def __init__(self, units: dict[int, dict[int, int]] | None = None):
        self.units = units or {}
        self.timeout = 3.0
        self.retries = 2
        self.stats = {"requests": 0}
        self.calls: list[tuple[int, int, int]] = []

    def read_holding_registers(self, address: int, quantity: int, unit_id: int = 1) -> list[int]:
        self.calls.append((address, quantity, unit_id))
        self.stats["requests"] += 1
        unit = self.units.get(unit_id)
        if unit is None:
            raise ModbusError(f"no response from unit {unit_id}")
        return [unit.get(address + offset, 0) for offset in range(quantity)]


class _Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        server: FakeDTU = self.server  # type: ignore[assignment]
        while True:
            header = self._read(7)
            if header is None:
                return
            tid, _protocol, _length, unit = struct.unpack(">HHHB", header)
            function = self._read(1)
            if function is None:
                return
            function = function[0]
            body = self._read(4)
            if body is None:
                return
            address, value = struct.unpack(">HH", body)
            server.requests.append((function, address, value, unit))
            if server.drop_connections:
                return
            registers = server.units.get(unit)
            if registers is None:
                self._exception(tid, unit, function, 0x0B)
            elif function == 3:
                if any(address + i not in registers for i in range(value)):
                    self._exception(tid, unit, function, 0x02)
                    continue
                payload = b"".join(struct.pack(">H", registers[address + i]) for i in range(value))
                pdu = bytes([3, len(payload)]) + payload
                self._reply(tid, unit, pdu)
            else:
                self._exception(tid, unit, function, 0x01)

    def _read(self, length: int) -> bytes | None:
        data = bytearray()
        while len(data) < length:
            try:
                chunk = self.request.recv(length - len(data))
            except OSError:
                return None
            if not chunk:
                return None
            data.extend(chunk)
        return bytes(data)

    def _reply(self, tid: int, unit: int, pdu: bytes) -> None:
        self.request.sendall(struct.pack(">HHHB", tid, 0, len(pdu) + 1, unit) + pdu)

    def _exception(self, tid: int, unit: int, function: int, code: int) -> None:
        self._reply(tid, unit, bytes([function | 0x80, code]))


class FakeDTU(socketserver.ThreadingTCPServer):
    """Tiny Modbus TCP server that serves Modbus function 3 (read holding registers)."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, units: dict[int, dict[int, int]] | None = None):
        super().__init__(("127.0.0.1", 0), _Handler)
        self.units: dict[int, dict[int, int]] = units or {}
        self.requests: list[tuple[int, int, int, int]] = []
        self.drop_connections = False
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return self.server_address[1]

    def add_microinverters(self, unit: int, inverters: list[list[int]], *, stride: int = 40) -> None:
        """Place each 20-register slot at 0x1000 + stride * index, as the reader expects."""
        registers = self.units.setdefault(unit, {})
        for index, slot in enumerate(inverters):
            base = 0x1000 + stride * index
            for offset, value in enumerate(slot):
                registers[base + offset] = value
        # Terminator slot: an all-zero serial tells the reader there are no more inverters.
        base = 0x1000 + stride * len(inverters)
        for offset in range(20):
            registers[base + offset] = 0

    def start(self) -> FakeDTU:
        self._thread.start()
        return self

    def stop(self) -> None:
        self.shutdown()
        self.server_close()


@pytest.fixture
def fake_dtu():
    server = FakeDTU().start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]

_CONFIG_VARIABLES = (
    "ACCESSORIES", "API_TOKEN", "CHINT_CANDIDATES", "HOY_MILES_TYPE", "HTTP_HOST", "HTTP_PORT",
    "LIMIT_REGISTER_ADDRESS", "LOG_DIR", "MAX_MICROINVERTERS", "METER_RETRY_SECONDS",
    "METER_PROBE_RETRY_SECONDS", "METER_WORD_ORDER", "MODBUS_RETRIES", "MODBUS_TIMEOUT",
    "POLL_INTERVAL", "TODAY_WH_MODE", "ENV_FILE",
)
_CONFIG_PREFIXES = ("DTU_", "HTTP_", "METER_", "CHINT_", "DTSU", "DDSU", "HOY_", "MODBUS_", "ACCESSORIES")


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    """Keep tests independent of the developer's shell, .env file and credentials.

    The whole environment is restored afterwards because load_env_file() writes to
    os.environ directly.
    """
    saved = os.environ.copy()
    for name in list(os.environ):
        if name in _CONFIG_VARIABLES or name.startswith(_CONFIG_PREFIXES):
            del os.environ[name]
    monkeypatch.chdir(tmp_path)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)
