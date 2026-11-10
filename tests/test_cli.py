from __future__ import annotations

import subprocess
import sys

import pytest

from hoymiles_dtu_reader import __version__
from hoymiles_dtu_reader.cli import build_parser, main


def test_version_command(capsys):
    main(["version"])
    assert capsys.readouterr().out.strip() == __version__


def test_python_dash_m_entry_point():
    result = subprocess.run(
        [sys.executable, "-m", "hoymiles_dtu_reader", "version"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == __version__


def test_only_the_local_reader_commands_are_registered():
    parser = build_parser()
    actions = [action for action in parser._actions if getattr(action, "choices", None)]
    assert set(actions[0].choices) == {"run", "version", "scan-meter"}


def test_scan_meter_needs_a_mode(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["scan-meter"])
    assert caught.value.code == 2
    assert "use --find" in capsys.readouterr().err


def test_scan_meter_refuses_the_dtu_slave_id(monkeypatch, capsys):
    monkeypatch.setenv("DTU_SLAVE_ID", "1")
    with pytest.raises(SystemExit):
        main(["scan-meter", "--slave", "1"])
    assert "DTU slave id" in capsys.readouterr().err


def test_scan_meter_find_against_a_fake_dtu(fake_dtu, monkeypatch, capsys):
    fake_dtu.units[4] = {0x2000: 0x4366, 0x2001: 0x0000}
    monkeypatch.setenv("DTU_IP", "127.0.0.1")
    monkeypatch.setenv("DTU_PORT", str(fake_dtu.port))
    main(["scan-meter", "--find", "--slaves", "4"])
    assert "slave   4: answers" in capsys.readouterr().out
