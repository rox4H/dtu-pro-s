# Security

This branch is a local, read-only data collector.

- The HTTP API binds to `127.0.0.1` by default. Authentication is optional; when `API_TOKEN` is set, every GET request must include `Authorization: Bearer <token>`.
- Paste a token issued by your own backend into `API_TOKEN`. This reader only compares the supplied token (using a constant-time comparison); it never creates, rotates or exposes tokens.
- To allow LAN access, set `HTTP_HOST=0.0.0.0` and restrict TCP port 5001 to trusted devices with a firewall.
- Bearer tokens are not encrypted by plain HTTP. Use a VPN or HTTPS reverse proxy over untrusted networks, and never publish the plain HTTP service directly to the Internet.
- The Modbus client only reads holding registers. There is no HTTP or Modbus write path.
- Do not include real inverter serial numbers, host names, private IP addresses or logs in public bug reports.

To report a security issue, use GitHub's private vulnerability reporting for this repository.
