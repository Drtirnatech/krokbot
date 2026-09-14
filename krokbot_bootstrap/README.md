# KrokBot Bootstrap Agent (`krokbot-bootstrap`)

A minimal (<30 MB) Alpine Linux container designed to deploy KrokBot agents onto blank Docker instances.

## Key Capabilities
- **Pre-flight Socket Check**: Validates that `/var/run/docker.sock` is mounted and responsive.
- **Zero Host Dependencies**: Requires only an active Docker engine on the target host (no Python, git, or systemd daemons needed).
- **Outbound Phone-Home**: Overcomes edge NAT, proxies, and firewalls with single-use 60-minute enrollment tokens.
- **Direct Stream Ingestion**: Pipes container image tarballs directly into `docker load` and streams GGUF weights into `/opt/krokbot/models/`.

## Manual Build
```bash
docker build -t krokbot-bootstrap:latest krokbot_bootstrap/
```

## Remote One-Line Invocation
```bash
docker run -d \
  --name krokbot-bootstrap \
  --restart on-failure \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /opt/krokbot:/host_opt_krokbot \
  -e C2_URL="http://<COMMAND_CENTER_IP>:5200" \
  -e ENROLLMENT_TOKEN="<ENROLLMENT_TOKEN>" \
  krokbot-bootstrap:latest
```
