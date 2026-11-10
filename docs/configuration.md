# Configuration

The example value `192.0.2.10` is reserved for documentation; replace it with the IP address of your DTU. The reader loads `.env` from the current directory. Set `ENV_FILE=/path/to/reader.env` in the process environment to use another file. Values already set in the process environment take priority. Restart the service after changing a value.

## DTU and polling

| Variable | Default | Meaning |
| --- | --- | --- |
| `DTU_IP` | `192.0.2.10` | DTU IP address or host name |
| `DTU_PORT` | `502` | Modbus TCP port |
| `DTU_SLAVE_ID` | `1` | Modbus unit ID of the DTU |
| `HOY_MILES_TYPE` | `HM` | Current scaling: `HM` or `MI` |
| `MODBUS_TIMEOUT` | `3` | Modbus connection/read timeout in seconds |
| `MODBUS_RETRIES` | `2` | Retries after a transport error |
| `POLL_INTERVAL` | `8` | Seconds between complete polling cycles |
| `MAX_MICROINVERTERS` | `100` | Maximum number of inverter slots to inspect |
| `LIMIT_REGISTER_ADDRESS` | `257` | Optional DTU power-limit register to read |
| `TODAY_WH_MODE` | `max` | `max` uses the largest port counter; `sum` adds all counters |

## CHINT meter (optional)

| Variable | Default | Meaning |
| --- | --- | --- |
| `ACCESSORIES` | empty | `ddsu666`, `dtsu666`, or both |
| `DDSU666_SLAVE_ID` | auto | Modbus address of the single-phase meter |
| `DTSU666_SLAVE_ID` | auto | Modbus address of the three-phase meter |
| `CHINT_SLAVE_ID` | empty | Shared fallback address for configured meters |
| `METER_SLAVE_ID` | empty | Legacy alias for `CHINT_SLAVE_ID` |
| `METER_PROBE` | automatic | `1` forces discovery; `0` disables discovery |
| `CHINT_CANDIDATES` | `2,3,4,11,22,101` | Slave addresses to probe |
| `METER_WORD_ORDER` | `low` | Float word order: `low` or `high` |
| `METER_RETRY_SECONDS` | `60` | Delay before retrying a failed pinned meter |
| `METER_PROBE_RETRY_SECONDS` | `300` | Delay before repeating meter discovery |

Set `ACCESSORIES=ddsu666` for a single-phase meter or `ACCESSORIES=dtsu666` for a three-phase meter. Leave it empty when no meter is connected.

## Local HTTP API and logs

| Variable | Default | Meaning |
| --- | --- | --- |
| `API_TOKEN` | empty | Optional company-issued bearer token; empty disables authentication |
| `HTTP_HOST` | `127.0.0.1` | Interface to listen on; use `0.0.0.0` only for trusted LAN access |
| `HTTP_PORT` | `5001` | HTTP port |
| `LOG_DIR` | `logs` | Directory for the rotating log file |

Paste the token issued by your company backend into `API_TOKEN`. The reader never generates, renews or manages it. When configured, clients must send it as `Authorization: Bearer <token>` on every GET request. Keep the default localhost binding unless another trusted device needs access, and use a firewall when binding to the LAN.
