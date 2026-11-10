from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from dataclasses import replace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from hoymiles_dtu_reader import __version__
from hoymiles_dtu_reader.aggregate import build_state
from hoymiles_dtu_reader.config import Settings
from hoymiles_dtu_reader.local_api import create_server
from hoymiles_dtu_reader.state import StateStore


def sample_state():
    return build_state(
        microinverters=[
            {"serial": "AA", "pv_power_w": 250.0, "today_wh": 10, "total_wh": 20, "link_status": 1}
        ],
        dtu_serial="DTU1",
        accessories=[{"type": "ddsu666", "slave_id": 4, "grid_power_w": -50.0}],
        limit_percent=100.0,
        diagnostics={"cycle": 3, "meter_type": "ddsu666"},
    )


@contextmanager
def running_api(state=None, token=""):
    settings = replace(Settings.from_env(), http_host="127.0.0.1", http_port=0, api_token=token)
    store = StateStore()
    if state is not None:
        store.set(state)
    server = create_server(store, settings)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def get_json(base_url, path, headers=None):
    request = Request(f"{base_url}{path}", headers=headers or {})
    with urlopen(request, timeout=3) as response:
        return response.status, response.headers, json.loads(response.read())


def test_health_before_the_first_sample():
    with running_api() as base_url:
        status, _, body = get_json(base_url, "/api/health")
    assert status == 200
    assert body["status"] == "starting"
    assert body["service"] == "hoymiles-dtu-reader"
    assert body["version"] == __version__


def test_health_after_a_sample():
    with running_api(sample_state()) as base_url:
        _, _, body = get_json(base_url, "/api/health")
    assert body["status"] == "online"
    assert body["dtu"] == "192.0.2.10:502"
    assert body["meter_type"] == "ddsu666"


def test_solar_endpoints():
    with running_api(sample_state()) as base_url:
        full = get_json(base_url, "/api/solar")[2]
        summary = get_json(base_url, "/api/solar/summary")[2]
        meter = get_json(base_url, "/api/solar/meter")[2]
        accessories = get_json(base_url, "/api/solar/accessories")[2]
        diagnostics = get_json(base_url, "/api/solar/diagnostics")[2]
    assert full["summary"]["pv_power_w"] == 250.0
    assert summary["grid_power_w"] == -50.0
    assert meter["type"] == "ddsu666"
    assert accessories[0]["slave_id"] == 4
    assert diagnostics["state"]["cycle"] == 3


def test_unmeasured_values_remain_null():
    state = build_state(
        microinverters=[],
        dtu_serial=None,
        accessories=[],
        limit_percent=None,
        diagnostics={},
    )
    with running_api(state) as base_url:
        body = get_json(base_url, "/api/solar/summary")[2]
    assert body["grid_power_w"] is None
    assert body["load_power_w"] is None


def test_api_is_no_store_and_cors_enabled():
    with running_api() as base_url:
        _, headers, _ = get_json(base_url, "/api/health", {"Origin": "http://dashboard.local"})
    assert headers["Cache-Control"] == "no-store"
    assert headers["Access-Control-Allow-Origin"] == "*"


def test_options_preflight_is_supported():
    with running_api() as base_url:
        request = Request(
            f"{base_url}/api/solar",
            method="OPTIONS",
            headers={"Origin": "http://dashboard.local"},
        )
        with urlopen(request, timeout=3) as response:
            assert response.status == 204
            assert response.headers["Access-Control-Allow-Methods"] == "GET, OPTIONS"
            assert "Authorization" in response.headers["Access-Control-Allow-Headers"]


def test_write_methods_are_rejected():
    with running_api() as base_url:
        request = Request(f"{base_url}/api/solar", data=b"{}", method="POST")
        with pytest.raises(HTTPError) as caught:
            urlopen(request, timeout=3)
    assert caught.value.code == 405
    assert json.loads(caught.value.read())["error"] == "method not allowed"


def test_configured_token_is_required_for_every_get_endpoint():
    with running_api(sample_state(), token="company-issued-token") as base_url:
        for path in ("/api/health", "/api/solar/summary"):
            with pytest.raises(HTTPError) as caught:
                urlopen(f"{base_url}{path}", timeout=3)
            assert caught.value.code == 401
            assert json.loads(caught.value.read()) == {"error": "unauthorized"}
            assert caught.value.headers["WWW-Authenticate"] == "Bearer"


def test_configured_token_is_accepted():
    with running_api(sample_state(), token="company-issued-token") as base_url:
        status, _, body = get_json(
            base_url,
            "/api/solar/summary",
            {"Authorization": "Bearer company-issued-token"},
        )
    assert status == 200
    assert body["pv_power_w"] == 250.0


def test_incorrect_token_is_rejected():
    with running_api(sample_state(), token="company-issued-token") as base_url:
        with pytest.raises(HTTPError) as caught:
            get_json(base_url, "/api/solar", {"Authorization": "Bearer wrong-token"})
    assert caught.value.code == 401


def test_unknown_endpoint_returns_404():
    with running_api() as base_url:
        with pytest.raises(HTTPError) as caught:
            urlopen(f"{base_url}/unknown", timeout=3)
    assert caught.value.code == 404
