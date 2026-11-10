from __future__ import annotations

import hmac
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from hoymiles_dtu_reader import __version__
from hoymiles_dtu_reader.config import Settings
from hoymiles_dtu_reader.state import StateStore

log = logging.getLogger("hoymiles_dtu_reader")


class ReaderHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def create_server(store: StateStore, settings: Settings) -> ReaderHTTPServer:
    """Create a read-only JSON server using only Python's standard library."""

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "HoymilesReader"
        sys_version = ""

        def log_message(self, fmt: str, *args) -> None:
            log.debug("HTTP %s - %s", self.address_string(), fmt % args)

        def end_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def send_json(
            self,
            payload: dict | list,
            status: int = 200,
            headers: dict[str, str] | None = None,
        ) -> None:
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def authorized(self) -> bool:
            expected = settings.api_token
            if not expected:
                return True
            authorization = self.headers.get("Authorization", "")
            scheme, separator, supplied = authorization.partition(" ")
            if not separator or scheme.lower() != "bearer" or not supplied:
                return False
            return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))

        def reject_write(self) -> None:
            self.close_connection = True
            self.send_json({"error": "method not allowed"}, status=405)

        def do_POST(self) -> None:
            self.reject_write()

        def do_PUT(self) -> None:
            self.reject_write()

        def do_DELETE(self) -> None:
            self.reject_write()

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:
            if not self.authorized():
                self.send_json(
                    {"error": "unauthorized"},
                    status=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                return

            path = urlsplit(self.path).path
            state = store.read()
            diagnostics = state.get("diagnostics", {})

            if path == "/api/health":
                payload = {
                    "status": state.get("status", "starting"),
                    "service": "hoymiles-dtu-reader",
                    "version": __version__,
                    "dtu": f"{settings.dtu_ip}:{settings.dtu_port}",
                    "meter_type": diagnostics.get("meter_type"),
                    "meter_slave": diagnostics.get("meter_slave"),
                    "chint_slave": diagnostics.get("chint_slave"),
                    "last_update": state.get("last_update"),
                }
            elif path == "/api/solar":
                payload = state
            elif path == "/api/solar/summary":
                payload = state.get("summary", {})
            elif path == "/api/solar/meter":
                payload = state.get("meter", {})
            elif path == "/api/solar/accessories":
                payload = state.get("accessories", [])
            elif path == "/api/solar/diagnostics":
                payload = {
                    "backend": f"hoymiles-dtu-reader/{__version__}",
                    "dtu": {
                        "ip": settings.dtu_ip,
                        "port": settings.dtu_port,
                        "slave_id": settings.dtu_slave_id,
                    },
                    "hoymiles_type": settings.hoymiles_type,
                    "accessories": list(settings.accessories),
                    "chint": {
                        "slave_id": diagnostics.get("chint_slave"),
                        "candidates": list(settings.meter_candidates),
                    },
                    "poll_interval": settings.poll_interval,
                    "modbus_timeout": settings.modbus_timeout,
                    "state": diagnostics,
                }
            else:
                self.send_json({"error": "not found"}, status=404)
                return

            self.send_json(payload)

    return ReaderHTTPServer((settings.http_host, settings.http_port), Handler)
