from __future__ import annotations

import pytest

from conftest import FakeModbus, microinverter_registers
from hoymiles_dtu_reader.devices.hoymiles import HoymilesDTU, decode_microinverter_block, registers_to_bytes
from hoymiles_dtu_reader.errors import ModbusError, ModbusExceptionResponse


def block(**kwargs) -> bytes:
    return registers_to_bytes(microinverter_registers(**kwargs))


def test_decodes_a_hm_microinverter_block():
    decoded = decode_microinverter_block(block(), "HM")
    assert decoded == {
        "data_type": 1,
        "serial": "112233445566",
        "port": 1,
        "pv_voltage_v": 32.5,
        "pv_current_a": 8.2,
        "grid_voltage_v": 231.4,
        "grid_freq_hz": 50.01,
        "pv_power_w": 266.5,
        "today_wh": 1200,
        "total_wh": 345678,
        "temperature_c": 31.5,
        "operating_status": 3,
        "alarm_code": 0,
        "alarm_count": 0,
        "link_status": 1,
    }


def test_mi_series_uses_a_different_current_scale():
    data = block(pv_current_a=8.2, hoymiles_type="MI")
    assert decode_microinverter_block(data, "MI")["pv_current_a"] == 8.2
    # The same raw bytes read as HM are ten times smaller.
    assert decode_microinverter_block(data, "HM")["pv_current_a"] == 0.82


def test_negative_temperature_is_signed():
    assert decode_microinverter_block(block(temperature_c=-5.5), "HM")["temperature_c"] == -5.5


def test_empty_serial_marks_the_end_of_the_list():
    assert decode_microinverter_block(block(serial="000000000000"), "HM") is None


def test_wrong_block_length_is_rejected():
    with pytest.raises(ModbusError):
        decode_microinverter_block(b"\x00" * 39, "HM")


def test_reads_all_microinverters_until_the_terminator():
    modbus = FakeModbus({1: {}})
    for index, serial in enumerate(["AA0000000001", "AA0000000002", "AA0000000003"]):
        for offset, value in enumerate(microinverter_registers(serial=serial)):
            modbus.units[1][0x1000 + 40 * index + offset] = value
    dtu = HoymilesDTU(modbus, unit_id=1, hoymiles_type="HM", max_inverters=100)
    assert [item["serial"] for item in dtu.read_all_microinverters()] == [
        "AA0000000001",
        "AA0000000002",
        "AA0000000003",
    ]


def test_max_inverters_caps_the_scan():
    modbus = FakeModbus({1: {}})
    for index in range(5):
        for offset, value in enumerate(microinverter_registers(serial=f"BB00000000{index:02d}")):
            modbus.units[1][0x1000 + 40 * index + offset] = value
    dtu = HoymilesDTU(modbus, unit_id=1, max_inverters=2)
    assert len(dtu.read_all_microinverters()) == 2


def test_reads_dtu_serial():
    modbus = FakeModbus({1: {0x2000: 0x1234, 0x2001: 0x5678, 0x2002: 0x9ABC}})
    assert HoymilesDTU(modbus, unit_id=1).read_dtu_serial() == "123456789ABC"


class LimitModbus:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = 0

    def read_holding_registers(self, address, quantity, unit_id=1):
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return [self.outcome]


def test_limit_percent_is_scaled():
    dtu = HoymilesDTU(LimitModbus(1000), unit_id=1)
    assert dtu.read_limit_percent(257) == 100.0
    assert dtu.limit_supported is True


def test_limit_register_refused_by_the_dtu_is_remembered():
    modbus = LimitModbus(ModbusExceptionResponse(3, 2))
    dtu = HoymilesDTU(modbus, unit_id=1)
    assert dtu.read_limit_percent(257) is None
    assert dtu.limit_supported is False
    assert dtu.read_limit_percent(257) is None
    assert modbus.calls == 1  # not polled again


def test_busy_exception_is_not_remembered():
    dtu = HoymilesDTU(LimitModbus(ModbusExceptionResponse(3, 6)), unit_id=1)
    with pytest.raises(ModbusExceptionResponse):
        dtu.read_limit_percent(257)
    assert dtu.limit_supported is None
