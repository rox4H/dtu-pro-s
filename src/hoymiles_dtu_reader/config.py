from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _csv_ints(value: str) -> tuple[int, ...]:
    return tuple(int(part.strip()) for part in value.split(",") if part.strip())


def load_env_file(path: str | None = None) -> str | None:
    """Load a small .env file without overriding values already in the process."""
    candidate = Path(path or os.getenv("ENV_FILE", "") or ".env")
    if not candidate.is_file():
        return None

    for raw in candidate.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if not separator or not key.strip():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)
    return str(candidate)


@dataclass(frozen=True)
class Settings:
    dtu_ip: str
    dtu_port: int
    dtu_slave_id: int
    hoymiles_type: str
    modbus_timeout: float
    modbus_retries: int
    poll_interval: float
    max_microinverters: int
    accessories: tuple[str, ...]
    meter_candidates: tuple[int, ...]
    meter_word_order: str
    meter_probe: bool
    dtsu_slave_id: int | None
    ddsu_slave_id: int | None
    limit_register_address: int
    api_token: str
    http_host: str
    http_port: int
    log_dir: str
    today_wh_mode: str = "max"
    meter_retry_seconds: float = 60.0
    meter_probe_retry_seconds: float = 300.0

    @classmethod
    def from_env(cls) -> Settings:
        hoymiles_type = os.getenv("HOY_MILES_TYPE", "HM").strip().upper()
        if hoymiles_type not in ("HM", "MI"):
            raise ValueError("HOY_MILES_TYPE must be HM or MI")

        word_order = os.getenv("METER_WORD_ORDER", "low").strip().lower()
        if word_order not in ("low", "high"):
            raise ValueError("METER_WORD_ORDER must be low or high")

        today_mode = os.getenv("TODAY_WH_MODE", "max").strip().lower()
        if today_mode not in ("max", "sum"):
            raise ValueError("TODAY_WH_MODE must be max or sum")

        accessories = tuple(
            value.strip().lower()
            for value in os.getenv("ACCESSORIES", "").split(",")
            if value.strip()
        )

        def optional_int(*names: str) -> int | None:
            for name in names:
                value = os.getenv(name, "").strip()
                if value:
                    return int(value)
            return None

        shared_slave = optional_int("CHINT_SLAVE_ID", "METER_SLAVE_ID")
        dtsu_slave_id = optional_int("DTSU666_SLAVE_ID")
        ddsu_slave_id = optional_int("DDSU666_SLAVE_ID")
        dtsu_slave_id = dtsu_slave_id if dtsu_slave_id is not None else shared_slave
        ddsu_slave_id = ddsu_slave_id if ddsu_slave_id is not None else shared_slave

        probe_value = os.getenv("METER_PROBE", "").strip()
        if probe_value == "1":
            meter_probe = True
            if not os.getenv("DTSU666_SLAVE_ID", "").strip():
                dtsu_slave_id = None
            if not os.getenv("DDSU666_SLAVE_ID", "").strip():
                ddsu_slave_id = None
        elif probe_value == "0":
            meter_probe = False
        else:
            meter_probe = dtsu_slave_id is None or ddsu_slave_id is None

        return cls(
            dtu_ip=os.getenv("DTU_IP", "192.0.2.10").strip(),
            dtu_port=_int("DTU_PORT", 502),
            dtu_slave_id=_int("DTU_SLAVE_ID", 1),
            hoymiles_type=hoymiles_type,
            modbus_timeout=_float("MODBUS_TIMEOUT", 3.0),
            modbus_retries=_int("MODBUS_RETRIES", 2),
            poll_interval=max(0.5, _float("POLL_INTERVAL", 8.0)),
            max_microinverters=max(1, _int("MAX_MICROINVERTERS", 100)),
            accessories=accessories,
            meter_candidates=_csv_ints(os.getenv("CHINT_CANDIDATES", "2,3,4,11,22,101")),
            meter_word_order=word_order,
            meter_probe=meter_probe,
            dtsu_slave_id=dtsu_slave_id,
            ddsu_slave_id=ddsu_slave_id,
            limit_register_address=_int("LIMIT_REGISTER_ADDRESS", 257),
            api_token=os.getenv("API_TOKEN", "").strip(),
            http_host=os.getenv("HTTP_HOST", "127.0.0.1").strip(),
            http_port=_int("HTTP_PORT", 5001),
            log_dir=os.getenv("LOG_DIR", "logs"),
            today_wh_mode=today_mode,
            meter_retry_seconds=max(0.0, _float("METER_RETRY_SECONDS", 60.0)),
            meter_probe_retry_seconds=max(0.0, _float("METER_PROBE_RETRY_SECONDS", 300.0)),
        )
