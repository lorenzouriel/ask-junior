# Traefik Reverse Proxy

Reverse proxy configuration for all Ask-Junior services.

## Services & Routes

| Service | URL | Port |
|---------|-----|------|
| Traefik Dashboard | http://traefik.local | 8080 |
| Agent (Chainlit) | http://agent.local | 8000 |
| Airflow | http://airflow.local | 8080 |
| Grafana | http://grafana.local | 3000 |
| Prometheus | http://prometheus.local | 9090 |
| Loki | http://loki.local | 3100 |
| Tempo | http://tempo.local | 3200 |
| Weaviate | http://weaviate.local | 8081 |

## Setup

### 1. Configure Hosts File (If running locally)
Add these entries to your hosts file:
**Windows**: `C:\Windows\System32\drivers\etc\hosts`
**Linux/Mac**: `/etc/hosts`

```bash
127.0.0.1 traefik.local
127.0.0.1 agent.local
127.0.0.1 airflow.local
127.0.0.1 grafana.local
127.0.0.1 prometheus.local
127.0.0.1 loki.local
127.0.0.1 tempo.local
127.0.0.1 weaviate.local
```

### 2. Start Other Services First

Ensure the external networks exist by starting the other services:

```bash
# Start all services (from project root)
cd ../agent && docker compose up -d
cd ../integrations && docker compose up -d
cd ../monitor && docker compose up -d
cd ../vector_database && docker compose up -d
```

### 3. Start Traefik

```bash
docker compose up -d
```

### 4. Access Services

- **Traefik Dashboard**: http://traefik.local:8080
- **All other services**: http://<service>.local

## Architecture

Traefik connects to all service networks:
- `ask-junior-network` - Agent service
- `airflow-network` - Airflow integrations
- `monitoring` - Grafana, Prometheus, Loki, Tempo
- `weaviate` - Vector database

## Troubleshooting

### Networks not found
If you get network errors, ensure the other services are running first to create the external networks.

### Service unreachable
Check that the service container is running and connected to the correct network:
```bash
docker network inspect <network-name>
```
