from __future__ import annotations

from hoymiles_dtu_reader.aggregate import build_state, meter_is_ok, pick_meter
from hoymiles_dtu_reader.state import StateStore


def inverter(power=100.0, today=500, total=10_000, linked=1, serial="AA"):
    return {
        "serial": serial,
        "pv_power_w": power,
        "today_wh": today,
        "total_wh": total,
        "link_status": linked,
    }


def meter(power=-40.0, kind="ddsu666"):
    return {
        "type": kind,
        "slave_id": 4,
        "grid_power_w": power,
        "importing": power > 5,
        "exporting": power < -5,
    }


def state(**overrides):
    kwargs = {
        "microinverters": [inverter()],
        "dtu_serial": "DTU1",
        "accessories": [],
        "limit_percent": None,
        "diagnostics": {},
    }
    kwargs.update(overrides)
    return build_state(**kwargs)


def test_without_a_meter_grid_and_load_are_unknown_not_zero():
    result = state()
    assert result["summary"]["grid_power_w"] is None
    assert result["summary"]["load_power_w"] is None
    assert result["summary"]["meter_ok"] is False
    assert result["summary"]["importing"] is False
    assert result["summary"]["exporting"] is False
    assert result["meter"] == {"error": "meter_not_configured"}


def test_load_is_pv_plus_grid_when_a_meter_works():
    result = state(microinverters=[inverter(300.0)], accessories=[meter(-100.0)])
    summary = result["summary"]
    assert summary["pv_power_w"] == 300.0
    assert summary["grid_power_w"] == -100.0
    assert summary["load_power_w"] == 200.0
    assert summary["exporting"] is True
    assert summary["meter_ok"] is True


def test_broken_meter_is_not_trusted():
    broken = {"type": "ddsu666", "error": "timeout", "grid_power_w": None}
    result = state(accessories=[broken])
    assert result["summary"]["meter_ok"] is False
    assert result["summary"]["grid_power_w"] is None


def test_unlinked_microinverters_do_not_contribute_power_or_total_energy():
    items = [inverter(200.0, total=100, linked=1), inverter(999.0, total=900, linked=0, serial="BB")]
    summary = state(microinverters=items)["summary"]
    assert summary["pv_power_w"] == 200.0
    assert summary["total_wh"] == 100


def test_today_energy_modes():
    items = [inverter(today=300), inverter(today=700, serial="BB")]
    assert state(microinverters=items, today_wh_mode="max")["summary"]["today_wh"] == 700
    assert state(microinverters=items, today_wh_mode="sum")["summary"]["today_wh"] == 1000
    diagnostics = state(microinverters=items)["diagnostics"]
    assert (diagnostics["today_wh_max"], diagnostics["today_wh_sum"]) == (700, 1000)


def test_limit_percent_is_rounded_and_optional():
    assert state(limit_percent=99.96)["limit_current_percent"] == 100.0
    assert state(limit_percent=None)["limit_current_percent"] is None


def test_meter_preference_order():
    readings = [meter(kind="dtsu666"), meter(kind="ddsu666")]
    assert pick_meter(readings)["type"] == "ddsu666"
    assert pick_meter([meter(kind="dtsu666")])["type"] == "dtsu666"
    assert pick_meter([]) == {"error": "meter_not_configured"}


def test_meter_is_ok_requires_a_value_and_no_error():
    assert meter_is_ok({"grid_power_w": 0.0}) is True
    assert meter_is_ok({"grid_power_w": None}) is False
    assert meter_is_ok({"grid_power_w": 1.0, "error": "x"}) is False


def test_diagnostics_carry_meter_and_inverter_details():
    result = state(accessories=[meter(kind="dtsu666")], diagnostics={"cycle": 7})
    diagnostics = result["diagnostics"]
    assert diagnostics["cycle"] == 7
    assert diagnostics["inverter_count"] == 1
    assert diagnostics["meter_type"] == "dtsu666"
    assert diagnostics["chint_slave"] == 4


def test_sample_timestamps_are_present():
    result = state()
    assert result["status"] == "online"
    assert result["sampled_at"].endswith("+00:00")
    assert len(result["last_update"]) == 19


def test_state_store_returns_independent_snapshots():
    store = StateStore()
    store.set({"status": "online", "summary": {"pv_power_w": 1}})
    snapshot = store.snapshot()
    snapshot["summary"]["pv_power_w"] = 999
    assert store.snapshot()["summary"]["pv_power_w"] == 1


def test_state_store_error_keeps_the_last_good_sample():
    store = StateStore()
    store.set({"status": "online", "summary": {"pv_power_w": 1}})
    store.mark_error(RuntimeError("boom"))
    snapshot = store.snapshot()
    assert snapshot["status"] == "error"
    assert snapshot["error"] == "boom"
    assert snapshot["summary"]["pv_power_w"] == 1


def test_state_store_error_before_the_first_sample():
    store = StateStore()
    store.mark_error(RuntimeError("down"))
    assert store.snapshot() == {"status": "error", "error": "down"}

def test_read_returns_the_published_sample_without_copying():
    store = StateStore()
    original = {"status": "online", "summary": {"pv_power_w": 10}}
    store.set(original)
    published = store.read()
    assert published is original

    store.mark_error(RuntimeError("temporary failure"))
    current = store.read()
    assert current is not published
    assert published["status"] == "online"
    assert current["status"] == "error"
    assert current["summary"] == {"pv_power_w": 10}



def test_state_store_read_returns_the_published_sample_without_copying():
    store = StateStore()
    sample = {"status": "online", "summary": {"pv_power_w": 123}}
    store.set(sample)
    assert store.read() is sample
