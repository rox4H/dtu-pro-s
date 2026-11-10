# AGENTS.md

Guidance for contributors and coding agents working on the minimal local reader.

## Purpose

This project reads Hoymiles microinverters through a DTU over Modbus TCP, optionally reads a CHINT DDSU666/DTSU666 meter, stores the latest sample in memory and exposes read-only JSON over local HTTP.

- Python 3.11+
- Runtime dependencies: none (standard library only)
- License: MIT
- Repository language: English

## Commands

```bash
pip install -e ".[dev]"
ruff check .
pytest
python -m build
hoymiles-dtu-reader
hoymiles-dtu-reader scan-meter --find
```

Run lint and tests before every commit. Tests use an in-process fake Modbus TCP server and do not require hardware or Internet access.

## Structure

```text
src/hoymiles_dtu_reader/
  cli.py                    command line and polling thread
  config.py                 .env loading and Settings
  transport/modbus_tcp.py   read-only Modbus TCP function 3 client
  devices/hoymiles.py       Hoymiles DTU and inverter decoder
  devices/meters/           CHINT meter readers
  factory.py                accessory construction
  poller.py                 one complete read cycle
  aggregate.py              normalized JSON state
  state.py                  thread-safe latest-sample store
  local_api.py              standard-library HTTP server
  scan.py                   read-only meter scanner
tests/                      offline protocol, decoder and API tests
packages/npm-client/        optional read-only JavaScript API client
docs/                       user and developer documentation
```

## Invariants

1. **Read-only:** only Modbus function 3 is supported. Do not add register writes or HTTP write routes.
2. **Local-only:** no Supabase, cloud sync, account pairing, generated credential files, cloud JWTs or remote upload code. The optional `API_TOKEN` is supplied and managed externally; this reader only validates it and never creates or rotates it.
3. **No runtime dependencies:** keep the Python runtime on the standard library. Dev-only tools belong in the optional `dev` extra.
4. **Immutable published samples:** after `StateStore.set()`, do not mutate that sample. The API reads it without copying; publish a new sample for each poll cycle.
5. **Truthful data:** an unmeasured value is `None` in Python and `null` in JSON. Never replace it with zero.
6. **Single source of settings:** environment variables are read only in `config.py`; document them in `.env.example` and `docs/configuration.md`.
7. **Language:** code, comments, tests, docs and commit messages are English.
8. **No real installation data:** never commit `.env`, device serials, hostnames, private IP addresses or logs from an actual installation.

## Data flow

`ModbusTCP -> HoymilesDTU + CHINT meters -> poll_once -> build_state -> StateStore -> HTTP JSON`.

The polling thread never waits for an external service. The API only returns a snapshot of the latest in-memory state; it does not query Modbus on an HTTP request.
