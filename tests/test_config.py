from __future__ import annotations

import pytest

from hoymiles_dtu_reader.config import Settings, load_env_file


def test_defaults():
    settings = Settings.from_env()
    assert (settings.dtu_ip, settings.dtu_port, settings.dtu_slave_id) == ("192.0.2.10", 502, 1)
    assert settings.hoymiles_type == "HM"
    assert settings.poll_interval == 8.0
    assert (settings.http_host, settings.http_port) == ("127.0.0.1", 5001)
    assert settings.accessories == ()
    assert settings.limit_register_address == 257
    assert settings.api_token == ""
    assert settings.today_wh_mode == "max"


def test_reads_values_from_the_environment(monkeypatch):
    monkeypatch.setenv("DTU_IP", "10.0.0.5")
    monkeypatch.setenv("DTU_PORT", "1502")
    monkeypatch.setenv("POLL_INTERVAL", "2.5")
    monkeypatch.setenv("ACCESSORIES", "DDSU666, dtsu666")
    monkeypatch.setenv("CHINT_CANDIDATES", "5, 6,7")
    monkeypatch.setenv("LIMIT_REGISTER_ADDRESS", "300")
    monkeypatch.setenv("API_TOKEN", "  company-issued-token  ")
    settings = Settings.from_env()
    assert settings.dtu_ip == "10.0.0.5"
    assert settings.dtu_port == 1502
    assert settings.poll_interval == 2.5
    assert settings.accessories == ("ddsu666", "dtsu666")
    assert settings.meter_candidates == (5, 6, 7)
    assert settings.limit_register_address == 300
    assert settings.api_token == "company-issued-token"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("HOY_MILES_TYPE", "XX"),
        ("METER_WORD_ORDER", "middle"),
        ("TODAY_WH_MODE", "median"),
    ],
)
def test_invalid_choices_are_rejected(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        Settings.from_env()


def test_hoymiles_type_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("HOY_MILES_TYPE", "mi")
    assert Settings.from_env().hoymiles_type == "MI"


def test_pinned_slave_ids_disable_probing(monkeypatch):
    monkeypatch.setenv("DDSU666_SLAVE_ID", "4")
    monkeypatch.setenv("DTSU666_SLAVE_ID", "5")
    settings = Settings.from_env()
    assert (settings.ddsu_slave_id, settings.dtsu_slave_id) == (4, 5)
    assert settings.meter_probe is False


def test_shared_slave_id_applies_to_both_meters(monkeypatch):
    monkeypatch.setenv("CHINT_SLAVE_ID", "7")
    settings = Settings.from_env()
    assert (settings.ddsu_slave_id, settings.dtsu_slave_id) == (7, 7)


def test_meter_probe_flag_forces_a_search(monkeypatch):
    monkeypatch.setenv("CHINT_SLAVE_ID", "7")
    monkeypatch.setenv("METER_PROBE", "1")
    settings = Settings.from_env()
    assert settings.meter_probe is True
    assert settings.ddsu_slave_id is None


def test_env_file_is_loaded_without_overriding_the_environment(tmp_path, monkeypatch):
    env_file = tmp_path / "custom.env"
    env_file.write_text(
        "﻿# comment\n"
        "DTU_IP=10.1.1.1\n"
        "export DTU_PORT=1503\n"
        "HTTP_HOST='0.0.0.0'\n"
        'LOG_DIR="/tmp/logs"\n'
        "not a pair\n"
        "=novalue\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DTU_PORT", "9999")
    assert load_env_file(str(env_file)) == str(env_file)
    settings = Settings.from_env()
    assert settings.dtu_ip == "10.1.1.1"
    assert settings.dtu_port == 9999
    assert settings.http_host == "0.0.0.0"
    assert settings.log_dir == "/tmp/logs"


def test_env_file_location_can_be_overridden(tmp_path, monkeypatch):
    env_file = tmp_path / "elsewhere.env"
    env_file.write_text("DTU_IP=10.2.2.2\n", encoding="utf-8")
    monkeypatch.setenv("ENV_FILE", str(env_file))
    assert load_env_file() == str(env_file)


def test_missing_env_file_is_not_an_error():
    assert load_env_file() is None
