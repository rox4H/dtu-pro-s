# Changelog

## 2.0.0 — minimal local edition (unreleased)

This release establishes the minimal, local-only reader as the installable distribution. It is read-only and does not include cloud account, pairing or upload functionality.

### Removed

- Supabase integration, cloud upload queue, account pairing, device credentials and cloud JWT authentication.
- HTTP register-write endpoint, write token and Modbus function 6. The reader is strictly read-only.
- Legacy response compatibility layer and its fabricated-zero behavior.

### Changed

- Replaced Flask and Flask-CORS with Python's built-in `http.server`.
- Removed all Python runtime dependencies.
- Kept Hoymiles and CHINT polling, decoding, aggregation, in-memory state, diagnostics and the read-only JSON API.
- Added optional API bearer-token validation for externally issued tokens; the reader does not generate or manage tokens.
- Updated the JavaScript client to send an optional externally supplied bearer token.

### Migration notes

- API response values that were not measured are returned as JSON `null`.
- The default API binding remains `127.0.0.1:5001`. Use `HTTP_HOST=0.0.0.0` only on a trusted LAN and protect it with a firewall.
- There is no historical database: only the most recent sample is kept in memory.
