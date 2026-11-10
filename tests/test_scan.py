from __future__ import annotations

import pytest

from conftest import FakeModbus
from hoymiles_dtu_reader.errors import ModbusError, ModbusExceptionResponse
from hoymiles_dtu_reader.scan import dump_registers, find_meters, parse_range, parse_slaves


def test_parse_range():
    assert parse_range("0x2000:50") == (0x2000, 50)
    assert parse_range("4096:10") == (4096, 10)
    assert parse_range("0x10") == (0x10, 20)  # default count


@pytest.mark.parametrize("text", ["0x10000:5", "0x10:0", "0x10:251", "zzz"])
def test_parse_range_rejects_invalid_values(text):
    with pytest.raises(ValueError):
        parse_range(text)


def test_parse_slaves():
    assert parse_slaves("1-3") == [1, 2, 3]
    assert parse_slaves("2, 3,22") == [2, 3, 22]


@pytest.mark.parametrize("text", ["0", "248", "1-300", ""])
def test_parse_slaves_rejects_invalid_values(text):
    with pytest.raises(ValueError):
        parse_slaves(text)


def test_find_meters_lists_answering_slaves_and_restores_settings():
    class Bus(FakeModbus):
        def read_holding_registers(self, address, quantity, unit_id=1):
            if unit_id == 5:
                raise ModbusExceptionResponse(3, 2)  # a device answered with an exception
            if unit_id == 7:
                return [0x4366, 0x0000]
            raise ModbusError("silence")

    bus = Bus()
    lines: list[str] = []
    assert find_meters(bus, [4, 5, 7], out=lines.append) == [5, 7]
    assert any("slave   5" in line for line in lines)
    assert any("slave   7" in line for line in lines)
    assert (bus.timeout, bus.retries) == (3.0, 2)


def test_find_meters_reports_when_nothing_answers():
    lines: list[str] = []
    assert find_meters(FakeModbus(), [1, 2], out=lines.append) == []
    assert lines == ["no slave answered"]


def test_dump_registers_prints_both_float_orders():
    bus = FakeModbus({4: {0x2000: 0x4366, 0x2001: 0x0000}})
    lines: list[str] = []
    dump_registers(bus, 4, [(0x2000, 2)], out=lines.append)
    text = "\n".join(lines)
    assert "# slave 4" in text
    assert "0x2000" in text
    assert "230" in text  # 0x43660000 as float32 is 230.0
    assert (bus.timeout, bus.retries) == (3.0, 2)
