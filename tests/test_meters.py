from __future__ import annotations

import pytest

from conftest import FakeModbus, chint_block, float32_registers
from hoymiles_dtu_reader.devices.meters import Ddsu666, Dtsu666
from hoymiles_dtu_reader.devices.meters.common import float32_from_words
from hoymiles_dtu_reader.errors import ModbusError


def meter_modbus(slave: int = 4, **block_kwargs) -> FakeModbus:
    registers = {0x2000 + i: value for i, value in enumerate(chint_block(**block_kwargs))}
    # Energy at 0x2048: two u32 values, high word first, scale 0.01 kWh.
    registers.update({0x2048: 0, 0x2049: 1234, 0x204A: 0, 0x204B: 567})
    return FakeModbus({slave: registers})


@pytest.mark.parametrize("low_word_first", [True, False])
def test_float32_word_order(low_word_first):
    registers = float32_registers(-123.5, low_word_first=low_word_first)
    assert float32_from_words(registers, 0, low_word_first) == -123.5


def test_wrong_word_order_decodes_garbage():
    registers = float32_registers(230.0, low_word_first=True)
    assert float32_from_words(registers, 0, False) != 230.0


def test_pinned_ddsu666_reads_a_single_phase_exporting_meter():
    modbus = meter_modbus(slave=4, total_power_w=-450.0, voltage_v=230.0, current_a=5.0)
    reading = Ddsu666(4, (), True).read(modbus)
    assert reading["type"] == "ddsu666"
    assert reading["slave_id"] == 4
    assert reading["grid_power_w"] == -450.0
    assert reading["grid_voltage_v"] == 230.0
    assert reading["grid_current_a"] == 5.0
    assert reading["exporting"] is True
    assert reading["importing"] is False
    assert reading["energy_imported_kwh"] == 12.34
    assert reading["energy_exported_kwh"] == 5.67
    assert "voltage_l2_v" not in reading


def test_dtsu666_publishes_all_three_phases():
    modbus = meter_modbus(slave=4, total_power_w=900.0, power_l1_w=300.0)
    reading = Dtsu666(4, (), True).read(modbus)
    assert reading["importing"] is True
    for key in ("voltage_l2_v", "voltage_l3_v", "current_l2_a", "current_l3_a", "power_l2_w", "power_l3_w"):
        assert key in reading


def test_small_power_is_neither_importing_nor_exporting():
    reading = Ddsu666(4, (), True).read(meter_modbus(total_power_w=3.0))
    assert reading["importing"] is False
    assert reading["exporting"] is False


def test_probe_finds_the_meter_on_a_candidate_slave():
    modbus = meter_modbus(slave=22)
    meter = Ddsu666(None, (2, 3, 22), True)
    reading = meter.read(modbus)
    assert meter.slave_id == 22
    assert reading["slave_id"] == 22
    assert "error" not in reading


def test_probe_restores_modbus_timeout_and_retries():
    modbus = meter_modbus(slave=22)
    modbus.timeout, modbus.retries = 3.0, 2
    Ddsu666(None, (2, 22), True).read(modbus)
    assert (modbus.timeout, modbus.retries) == (3.0, 2)


def test_probe_rejects_implausible_voltage():
    modbus = meter_modbus(slave=3, voltage_v=5.0)
    meter = Ddsu666(None, (3,), True)
    assert meter.read(modbus)["error"] == "meter_not_found"
    assert meter.slave_id is None


def test_failing_meter_backs_off_instead_of_polling_every_cycle():
    now = [1000.0]
    modbus = FakeModbus({})  # nothing answers
    meter = Ddsu666(4, (), True, retry_seconds=60.0, clock=lambda: now[0])

    first = meter.read(modbus)
    assert first["grid_power_w"] is None
    assert first["error"]
    calls_after_first = len(modbus.calls)

    now[0] += 30
    assert meter.read(modbus)["grid_power_w"] is None
    assert len(modbus.calls) == calls_after_first  # still backing off

    now[0] += 31
    meter.read(modbus)
    assert len(modbus.calls) > calls_after_first  # retried after the delay


def test_meter_recovers_after_a_failure():
    now = [0.0]
    modbus = FakeModbus({})
    meter = Ddsu666(4, (), True, retry_seconds=10.0, clock=lambda: now[0])
    assert meter.read(modbus)["error"]
    modbus.units.update(meter_modbus(slave=4).units)
    now[0] += 11
    assert meter.read(modbus)["grid_power_w"] == -450.0


def test_failed_read_of_optional_registers_does_not_fail_the_reading():
    modbus = meter_modbus(slave=4)

    original = modbus.read_holding_registers

    def flaky(address, quantity, unit_id=1):
        if address in (0x202C, 0x2048):
            raise ModbusError("optional register unavailable")
        return original(address, quantity, unit_id)

    modbus.read_holding_registers = flaky
    reading = Ddsu666(4, (), True).read(modbus)
    assert reading["grid_power_w"] == -450.0
    assert reading["energy_imported_kwh"] == 0.0
