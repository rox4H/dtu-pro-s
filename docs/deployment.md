# Deployment

The reader is a single local process with no runtime Python dependencies and no external service requirements.

## Linux with systemd

Install Python 3.11 or later and the reader:

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin hoymiles
sudo python3 -m venv /opt/hoymiles-dtu-reader
sudo /opt/hoymiles-dtu-reader/bin/pip install .
sudo install -d -m 750 -o hoymiles -g hoymiles /etc/hoymiles-dtu-reader
sudo install -m 640 -o hoymiles -g hoymiles .env.example /etc/hoymiles-dtu-reader/reader.env
```

Create `/etc/systemd/system/hoymiles-dtu-reader.service`:

```ini
[Unit]
Description=Hoymiles DTU Reader
After=network-online.target
Wants=network-online.target

[Service]
User=hoymiles
Group=hoymiles
WorkingDirectory=/var/lib/hoymiles-dtu-reader
Environment=ENV_FILE=/etc/hoymiles-dtu-reader/reader.env
Environment=LOG_DIR=/var/log/hoymiles-dtu-reader
StateDirectory=hoymiles-dtu-reader
LogsDirectory=hoymiles-dtu-reader
ExecStart=/opt/hoymiles-dtu-reader/bin/hoymiles-dtu-reader
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Enable the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hoymiles-dtu-reader
journalctl -u hoymiles-dtu-reader -f
```

## Docker Compose

```yaml
services:
  hoymiles-dtu-reader:
    build: .
    restart: unless-stopped
    env_file: .env
    ports:
      - "127.0.0.1:5001:5001"
    volumes:
      - hoymiles-dtu-data:/data

volumes:
  hoymiles-dtu-data:
```

The container listens on all interfaces internally. Publish the port on localhost unless a trusted LAN client needs to connect. The Docker health check automatically uses `API_TOKEN` when it is configured.

## Network exposure

The API listens on `127.0.0.1` by default. Set `API_TOKEN` to the value issued by your company backend; clients must send `Authorization: Bearer <token>`. To allow another device on your LAN, set `HTTP_HOST=0.0.0.0` and restrict TCP port 5001 to trusted devices with a firewall. The token is sent over HTTP, so use a VPN or HTTPS reverse proxy for traffic across untrusted networks. Never publish the plain HTTP service directly to the public Internet.
