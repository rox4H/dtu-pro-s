# Architecture

One Python process reads the DTU, optionally reads a CHINT meter, stores the latest sample in memory and serves it over HTTP.

```text
Hoymiles DTU --Modbus TCP--+
                           +--> poll_once --> build_state --> StateStore --> HTTP JSON API
CHINT meter --via DTU------+
```

## Runtime

- The main thread serves the local API with Python's `ThreadingHTTPServer`.
- One daemon thread polls the DTU every `POLL_INTERVAL` seconds.
- `StateStore` atomically publishes each complete sample. The API uses `read()` to serialize the published sample without a deep copy; `snapshot()` remains available when an independent mutable copy is needed.
- No cloud thread, upload queue, network account, credentials file or database is used.

## Reading cycle

1. Read inverter slots from register `0x1000` until the first empty serial or `MAX_MICROINVERTERS`.
2. Read the DTU serial number and, when supported, its current power limit.
3. Read configured CHINT meters. A failed meter does not stop the inverter read.
4. Aggregate PV, grid and household-load values. Unmeasured values remain `null`.
5. Save the complete sample in `StateStore`. HTTP requests return a snapshot of this state.

## Modules

| Module | Responsibility |
| --- | --- |
| `transport/modbus_tcp.py` | Read-only Modbus TCP function 3 client |
| `devices/hoymiles.py` | Inverter and DTU register decoder |
| `devices/meters/` | CHINT meter discovery, decoding and retry timing |
| `factory.py` | Builds configured meter readers |
| `poller.py` | One complete polling cycle |
| `aggregate.py` | Builds the coherent JSON state |
| `state.py` | Thread-safe latest-sample store |
| `local_api.py` | Standard-library HTTP JSON endpoints |
| `scan.py` | Read-only register discovery utility |

## Design

- **Read-only:** the Modbus client only sends function 3 requests; no register-write method or HTTP write endpoint exists.
- **Local first:** polling and the HTTP API have no dependency on external services.
- **Honest values:** an unmeasured value remains `None` and is encoded as JSON `null`.
- **Small runtime:** Python standard library only; no web framework or cloud SDK.
- **Fault isolation:** a failed polling cycle is recorded and retried on the next cycle.
