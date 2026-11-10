from __future__ import annotations

from hoymiles_dtu_reader.config import Settings
from hoymiles_dtu_reader.devices.meters.ddsu666 import Ddsu666
from hoymiles_dtu_reader.devices.meters.dtsu666 import Dtsu666


def probe_candidates(settings: Settings, slave_id: int | None) -> tuple[int, ...]:
    if slave_id is not None or not settings.meter_probe:
        return ()
    return tuple(
        candidate
        for candidate in settings.meter_candidates
        if candidate != settings.dtu_slave_id
    )


def build_accessories(settings: Settings) -> list:
    low_word_first = settings.meter_word_order == "low"
    timing = {
        "retry_seconds": settings.meter_retry_seconds,
        "probe_retry_seconds": settings.meter_probe_retry_seconds,
    }
    accessories = []
    for name in settings.accessories:
        if name == "dtsu666":
            accessories.append(
                Dtsu666(
                    settings.dtsu_slave_id,
                    probe_candidates(settings, settings.dtsu_slave_id),
                    low_word_first,
                    **timing,
                )
            )
        elif name == "ddsu666":
            accessories.append(
                Ddsu666(
                    settings.ddsu_slave_id,
                    probe_candidates(settings, settings.ddsu_slave_id),
                    low_word_first,
                    **timing,
                )
            )
        else:
            known = "dtsu666, ddsu666"
            raise ValueError(f"Unknown accessory '{name}'. Known: {known}")

    slaves = [item.slave_id for item in accessories if item.slave_id is not None]
    if len(slaves) != len(set(slaves)):
        raise ValueError(
            "Two accessories are configured with the same Modbus slave id. "
            "Set DTSU666_SLAVE_ID and DDSU666_SLAVE_ID to different values."
        )
    return accessories
