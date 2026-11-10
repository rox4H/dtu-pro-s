# HTTP API

The reader exposes a read-only JSON API on `HTTP_HOST:HTTP_PORT` (defaults to `127.0.0.1:5001`).

Authentication is optional. When `API_TOKEN` is empty, no token is required. When it is configured, every GET endpoint (including `/api/health`) requires the company-issued token in `Authorization: Bearer <token>`. The reader only checks the supplied value; it does not create, renew or manage tokens. OPTIONS preflight requests remain unauthenticated so browsers can send the authorization header. Only GET and OPTIONS are supported. Responses include `Cache-Control: no-store`.

Example:

```bash
curl -H "Authorization: Bearer YOUR_COMPANY_TOKEN" http://127.0.0.1:5001/api/solar/summary
```

Requests with a missing or incorrect token return HTTP `401` and `{"error":"unauthorized"}`.

## Endpoints

| Method | Path | Response |
| --- | --- | --- |
| GET | `/api/health` | Status, version, DTU and last update |
| GET | `/api/solar` | Complete current state |
| GET | `/api/solar/summary` | Aggregated power and energy values |
| GET | `/api/solar/meter` | Selected CHINT meter reading |
| GET | `/api/solar/accessories` | All configured accessory readings |
| GET | `/api/solar/diagnostics` | Polling and Modbus diagnostics |

Unknown paths return HTTP 404. POST, PUT and DELETE are rejected with HTTP 405.

## Summary example

```json
{
  "pv_power_w": 266.5,
  "grid_power_w": -120.0,
  "load_power_w": 146.5,
  "today_wh": 1200,
  "total_wh": 345678,
  "importing": false,
  "exporting": true,
  "meter_ok": true
}
```

- Positive `grid_power_w` means import from the grid.
- Negative `grid_power_w` means export to the grid.
- `load_power_w` is PV power plus grid power and is only known when the meter works.
- `today_wh` uses the largest inverter-port counter by default. Set `TODAY_WH_MODE=sum` to add all ports.
- Without a meter, grid and load values are `null`.

## Full snapshot

`GET /api/solar` returns:

| Field | Meaning |
| --- | --- |
| `status` | `online` or `error` |
| `sampled_at` | Sample timestamp in UTC |
| `last_update` | Local display timestamp |
| `dtu` | DTU serial number, if readable |
| `limit_current_percent` | Current power limit, if supported |
| `summary` | Aggregated PV, grid, load and energy values |
| `meter` | Selected CHINT meter |
| `accessories` | All configured meter readings |
| `microinverters` | One object per inverter port |
| `diagnostics` | Poll cycle, timing, Modbus counters and meter status |

The service stores only the latest sample in memory. It does not provide historical storage.
