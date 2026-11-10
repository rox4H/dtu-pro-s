from __future__ import annotations

from datetime import UTC, datetime


def pick_meter(readings: list[dict]) -> dict:
    for preferred in ("ddsu666", "dtsu666"):
        for reading in readings:
            if reading.get("type") == preferred:
                return reading
    if readings:
        return readings[0]
    return {"error": "meter_not_configured"}


def meter_is_ok(meter: dict) -> bool:
    return not meter.get("error") and meter.get("grid_power_w") is not None


def build_state(
    *,
    microinverters: list[dict],
    dtu_serial: str | None,
    accessories: list[dict],
    limit_percent: float | None,
    diagnostics: dict,
    today_wh_mode: str = "max",
) -> dict:
    """Build one coherent sample.

    Values that were not measured are None, never 0. A missing meter must not
    look like "no grid exchange", and load is only known with a working meter.
    """
    linked = [item for item in microinverters if item.get("link_status", 0)]
    total_pv = sum(item.get("pv_power_w", 0) for item in linked)
    today_values = [item.get("today_wh", 0) for item in microinverters]
    today_max = max(today_values, default=0)
    today_sum = sum(today_values)
    total_wh = sum(item.get("total_wh", 0) for item in linked)

    meter = pick_meter(accessories)
    meter_ok = meter_is_ok(meter)
    grid_w = meter["grid_power_w"] if meter_ok else None
    chint = next((item for item in accessories if item.get("type") == "dtsu666"), None)

    return {
        "status": "online",
        "sampled_at": datetime.now(UTC).isoformat(),
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dtu": dtu_serial,
        "limit_current_percent": None if limit_percent is None else round(limit_percent, 1),
        "summary": {
            "pv_power_w": round(total_pv, 1),
            "grid_power_w": None if grid_w is None else round(grid_w, 1),
            "load_power_w": None if grid_w is None else round(total_pv + grid_w, 1),
            "today_wh": int(today_sum if today_wh_mode == "sum" else today_max),
            "total_wh": int(total_wh),
            "importing": bool(meter.get("importing", False)) if meter_ok else False,
            "exporting": bool(meter.get("exporting", False)) if meter_ok else False,
            "meter_ok": meter_ok,
        },
        "meter": meter,
        "accessories": accessories,
        "microinverters": microinverters,
        "diagnostics": {
            **diagnostics,
            "inverter_count": len(microinverters),
            "meter_type": meter.get("type"),
            "meter_slave": meter.get("slave_id"),
            "chint_slave": None if chint is None else chint.get("slave_id"),
            # Publish both totals so they can be compared with the Hoymiles app.
            "today_wh_max": int(today_max),
            "today_wh_sum": int(today_sum),
        },
    }
