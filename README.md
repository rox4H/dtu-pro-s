# Hoymiles DTU Reader

A lightweight, read-only Python service for collecting data from Hoymiles microinverters through a DTU over Modbus TCP. It exposes the latest measurements through a local JSON HTTP API.

An optional CHINT DDSU666 (single-phase) or DTSU666 (three-phase) meter can also be read from the DTU's RS485 bus.

## Features

- Reads inverter power, voltage, current, temperature and energy counters.
- Reads the DTU serial number and power-limit percentage when the register is supported.
- Optionally reads a CHINT grid meter and calculates grid exchange and household load.
- Keeps the latest complete sample in memory.
- Exposes read-only HTTP GET endpoints; no Modbus register writes are supported.
- Uses only the Python standard library at runtime.
- Supports an optional bearer token issued by an external backend. The reader never creates, rotates or manages tokens.
- Works locally without cloud services or an Internet connection after installation.

## Requirements

- Python 3.11 or later.
- A Hoymiles DTU reachable over Modbus TCP.
- Optional CHINT DDSU666 or DTSU666 meter connected to the DTU's RS485 bus.

## Install

Create and activate a virtual environment, then install the package from PyPI:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install hoymiles-dtu-reader
```

## Configure

Download the example configuration into the directory from which you will run the reader:

```bash
curl -fsSLo .env https://raw.githubusercontent.com/rox4H/dtu-pro-s/main/.env.example
```

Edit `.env` and replace the documentation-only `DTU_IP=192.0.2.10` with the IP address of your DTU. The operating system's environment variables take precedence over values in `.env`.

For a CHINT meter, set `ACCESSORIES=ddsu666` or `ACCESSORIES=dtsu666`. Set its Modbus address in `DDSU666_SLAVE_ID` or `DTSU666_SLAVE_ID`; otherwise the reader searches `CHINT_CANDIDATES`.

See [the configuration guide](docs/configuration.md) for every setting.

## Run

```bash
hoymiles-dtu-reader
```

To scan for a compatible CHINT meter once:

```bash
hoymiles-dtu-reader scan-meter --find
```

## HTTP API

The service listens on `http://127.0.0.1:5001` by default.

| Endpoint | Returns |
| --- | --- |
| `GET /api/health` | Service status, version, DTU and last update |
| `GET /api/solar` | Complete current snapshot |
| `GET /api/solar/summary` | PV, grid and household-load summary |
| `GET /api/solar/meter` | CHINT meter reading |
| `GET /api/solar/accessories` | Configured meters and readings |
| `GET /api/solar/diagnostics` | DTU, polling and Modbus diagnostics |

Example:

```bash
curl http://127.0.0.1:5001/api/solar/summary

# When API_TOKEN is configured:
curl -H "Authorization: Bearer <token>" http://127.0.0.1:5001/api/solar/summary
```

The API is read-only and binds to localhost by default. Authentication is optional: paste a token issued by your backend into `API_TOKEN` in `.env`. When configured, every GET endpoint requires `Authorization: Bearer <token>`. Leave `API_TOKEN` empty to disable authentication. To allow another device on a trusted LAN, set `HTTP_HOST=0.0.0.0` and restrict port 5001 with your firewall. Do not expose the plain HTTP API directly to the Internet.

All measurements use watts and watt-hours unless a field says otherwise. A value that could not be measured is `null`, not a fabricated zero.

## Runtime footprint

- Python 3.11+
- No runtime Python dependencies.
- One polling thread and one lightweight threaded HTTP server.
- No cloud worker, queue, credentials store, database client or write endpoint.

## Further information

- [Deployment guide](docs/deployment.md)
- [API reference](docs/api.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [GitHub repository](https://github.com/rox4H/dtu-pro-s)

## License

[MIT](LICENSE). Hoymiles and CHINT are trademarks of their respective owners. This project is independent and is not affiliated with, endorsed by or sponsored by them.
