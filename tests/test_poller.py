"""End-to-end poll against a fake Modbus TCP DTU: transport -> decoders -> aggregation."""
from __future__ import annotations

import pytest

from conftest import chint_block, microinverter_registers
from hoymiles_dtu_reader.config import Settings
from hoymiles_dtu_reader.devices.hoymiles import HoymilesDTU
from hoymiles_dtu_reader.factory import build_accessories
from hoymiles_dtu_reader.poller import poll_once
from hoymiles_dtu_reader.transport.modbus_tcp import ModbusTCP


def populate(server, *, with_limit=True, with_meter=True):
    server.add_microinverters(
        1,
        [
            microinverter_registers(serial="AA0000000001", port=1, pv_power_w=200.0, today_wh=900),
            microinverter_registers(serial="AA0000000001", port=2, pv_power_w=100.0, today_wh=700),
            microinverter_registers(
                serial="BB0000000002", port=1, pv_power_w=50.0, today_wh=100, link_status=0
            ),
        ],
    )
    server.units[1].update({0x2000: 0x1234, 0x2001: 0x5678, 0x2002: 0x9ABC})
    if with_limit:
        server.units[1][257] = 1000
    if with_meter:
        registers = {0x2000 + i: value for i, value in enumerate(chint_block(total_power_w=-120.0))}
        registers.update({0x2048: 0, 0x2049: 100, 0x204A: 0, 0x204B: 200})
        server.units[4] = registers


def run_poll(server, monkeypatch, **env):
    monkeypatch.setenv("DTU_IP", "127.0.0.1")
    monkeypatch.setenv("DTU_PORT", str(server.port))
    monkeypatch.setenv("MODBUS_TIMEOUT", "1")
    monkeypatch.setenv("MODBUS_RETRIES", "0")
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    settings = Settings.from_env()
    modbus = ModbusTCP(settings.dtu_ip, settings.dtu_port, settings.modbus_timeout, settings.modbus_retries)
    hoymiles = HoymilesDTU(modbus, settings.dtu_slave_id, settings.hoymiles_type, settings.max_microinverters)
    try:
        return poll_once(modbus, hoymiles, build_accessories(settings), settings, cycle=1)
    finally:
        modbus.close()


def test_full_poll_with_a_pinned_ddsu666(fake_dtu, monkeypatch):
    populate(fake_dtu)
    state = run_poll(fake_dtu, monkeypatch, ACCESSORIES="ddsu666", DDSU666_SLAVE_ID="4")

    assert state["status"] == "online"
    assert state["dtu"] == "123456789ABC"
    assert state["limit_current_percent"] == 100.0
    assert len(state["microinverters"]) == 3

    summary = state["summary"]
    assert summary["pv_power_w"] == 300.0  # the unlinked inverter is ignored
    assert summary["grid_power_w"] == -120.0
    assert summary["load_power_w"] == 180.0
    assert summary["exporting"] is True
    assert summary["meter_ok"] is True
    assert summary["today_wh"] == 900

    diagnostics = state["diagnostics"]
    assert diagnostics["cycle"] == 1
    assert diagnostics["accessories"] == ["ddsu666"]
    assert diagnostics["inverter_count"] == 3
    assert diagnostics["modbus"]["requests"] > 0


def test_poll_without_accessories_reports_unknown_grid_values(fake_dtu, monkeypatch):
    populate(fake_dtu, with_meter=False)
    state = run_poll(fake_dtu, monkeypatch)
    assert state["summary"]["pv_power_w"] == 300.0
    assert state["summary"]["grid_power_w"] is None
    assert state["summary"]["load_power_w"] is None
    assert state["meter"] == {"error": "meter_not_configured"}


def test_a_dtu_that_refuses_the_limit_register_still_polls(fake_dtu, monkeypatch):
    populate(fake_dtu, with_limit=False, with_meter=False)
    state = run_poll(fake_dtu, monkeypatch)
    assert state["limit_current_percent"] is None
    assert state["diagnostics"]["limit_supported"] is False


def test_a_missing_meter_does_not_break_the_dtu_reading(fake_dtu, monkeypatch):
    populate(fake_dtu, with_meter=False)
    state = run_poll(fake_dtu, monkeypatch, ACCESSORIES="ddsu666", DDSU666_SLAVE_ID="4")
    assert state["summary"]["pv_power_w"] == 300.0
    assert state["summary"]["meter_ok"] is False
    assert state["meter"]["error"]


def test_the_meter_is_found_by_probing_candidate_slaves(fake_dtu, monkeypatch):
    populate(fake_dtu)
    state = run_poll(
        fake_dtu, monkeypatch, ACCESSORIES="ddsu666", METER_PROBE="1", CHINT_CANDIDATES="2,3,4"
    )
    assert state["meter"]["slave_id"] == 4
    assert state["summary"]["meter_ok"] is True


def test_duplicate_meter_slave_ids_are_rejected(monkeypatch):
    monkeypatch.setenv("ACCESSORIES", "ddsu666,dtsu666")
    monkeypatch.setenv("CHINT_SLAVE_ID", "4")
    with pytest.raises(ValueError, match="same Modbus slave id"):
        build_accessories(Settings.from_env())


def test_unknown_accessories_are_rejected(monkeypatch):
    monkeypatch.setenv("ACCESSORIES", "toaster")
    with pytest.raises(ValueError, match="toaster"):
        build_accessories(Settings.from_env())
