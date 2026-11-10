# hoymiles-dtu-reader-client

Small read-only JavaScript/TypeScript client for the local JSON API of **Hoymiles DTU Reader**.

The Python service must be installed and running separately.

## Requirements

- Node.js 22 or later (built-in `fetch`).
- Hoymiles DTU Reader, normally at `http://127.0.0.1:5001`.

## Install from a source checkout

The JavaScript client is included in this repository but is not published to npm as a separate package.

```bash
npm install /path/to/dtu-pro-s/packages/npm-client
```

## Usage

```js
import { HoymilesReaderClient } from "hoymiles-dtu-reader-client";

const reader = new HoymilesReaderClient({
  baseUrl: "http://127.0.0.1:5001",
  token: process.env.HOYMILES_API_TOKEN, // same company-issued token configured as API_TOKEN on the reader
  timeoutMs: 5000,
});

const health = await reader.getHealth();
const summary = await reader.getSummary();
const snapshot = await reader.getSolar();

console.log(health.status, summary.pv_power_w, snapshot.microinverters);
```

## API methods

| Method | Endpoint |
| --- | --- |
| `getHealth()` | `GET /api/health` |
| `getSolar()` | `GET /api/solar` |
| `getMeter()` | `GET /api/solar/meter` |
| `getSummary()` | `GET /api/solar/summary` |
| `getAccessories()` | `GET /api/solar/accessories` |
| `getDiagnostics()` | `GET /api/solar/diagnostics` |

All methods are read-only. The optional `token` option sends `Authorization: Bearer <token>`; it must match the value configured as `API_TOKEN` on the Python reader. The client never creates or stores tokens. Omit `token` when authentication is disabled on the reader.

## Errors

- `HoymilesApiError`: the API returned a non-success HTTP status.
- `HoymilesConnectionError`: the service could not be reached.
- `HoymilesTimeoutError`: the request exceeded `timeoutMs`.

## License

[MIT](LICENSE)
