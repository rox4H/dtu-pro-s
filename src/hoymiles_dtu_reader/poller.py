from __future__ import annotations

import logging
import time

from hoymiles_dtu_reader.aggregate import build_state
from hoymiles_dtu_reader.config import Settings
from hoymiles_dtu_reader.devices.hoymiles import HoymilesDTU

log = logging.getLogger("hoymiles_dtu_reader")


def poll_once(
    modbus,
    hoymiles: HoymilesDTU,
    accessories: list,
    settings: Settings,
    cycle: int = 0,
) -> dict:
    started = time.monotonic()
    microinverters = hoymiles.read_all_microinverters()

    dtu_serial = None
    try:
        dtu_serial = hoymiles.read_dtu_serial()
    except Exception as exc:
        log.warning("Could not read DTU serial: %s", exc)

    readings = [accessory.read(modbus) for accessory in accessories]

    limit_percent = None
    try:
        limit_percent = hoymiles.read_limit_percent(settings.limit_register_address)
    except Exception as exc:
        log.warning("Could not read power limit: %s", exc)

    return build_state(
        microinverters=microinverters,
        dtu_serial=dtu_serial,
        accessories=readings,
        limit_percent=limit_percent,
        today_wh_mode=settings.today_wh_mode,
        diagnostics={
            "cycle": cycle,
            "limit_supported": hoymiles.limit_supported,
            "poll_time_ms": round((time.monotonic() - started) * 1000, 1),
            "modbus": dict(modbus.stats),
            "accessories": [accessory.type_name for accessory in accessories],
        },
    )
