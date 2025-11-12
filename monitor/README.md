# Greenhouse Monitoring Stack

A production-ready observability stack using OpenTelemetry, Prometheus, Loki, Tempo, and Grafana.

## Architecture

This stack implements the three pillars of observability:

- **Metrics**: Prometheus for metrics storage and querying
- **Logs**: Loki for log aggregation and searching
- **Traces**: Tempo for distributed tracing

### Components

1. **OpenTelemetry Collector** - Central telemetry data hub
   - Receives metrics, logs, and traces via OTLP
   - Routes data to appropriate backends
   - Port 4317 (gRPC), 4318 (HTTP), 9464 (metrics)

2. **Prometheus** - Metrics storage and alerting
   - Scrapes metrics from applications and services
   - Web UI: http://localhost:9090

3. **Loki** - Log aggregation system
   - Stores and indexes logs efficiently
   - API: http://localhost:3100

4. **Tempo** - Distributed tracing backend
   - Stores and queries traces
   - API: http://localhost:3200

5. **Grafana** - Unified visualization platform
   - Pre-configured datasources for all backends
   - Web UI: http://localhost:3000
   - Default credentials: admin/admin

6. **Greenhouse App** - Sample Python application
   - Instrumented with OpenTelemetry
   - Exposes Prometheus metrics on port 8000

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- At least 4GB of available RAM
- Ports 3000, 3100, 3200, 4317, 4318, 8000, 9090, 9464 available

### Start the Stack

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Check service health
docker-compose ps
```

### Access the Services

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Loki**: http://localhost:3100
- **Tempo**: http://localhost:3200
- **App Metrics**: http://localhost:8000

## Using Grafana

1. Open http://localhost:3000
2. Login with admin/admin (change password on first login)
3. Datasources are pre-configured:
   - **Prometheus** - Default datasource for metrics
   - **Loki** - Log queries and exploration
   - **Tempo** - Trace visualization with correlation to logs and metrics

### Exploring Data

#### Metrics (Prometheus)
1. Go to Explore → Select Prometheus
2. Query example: `rate(app_requests_total[5m])`
3. View application request rates and custom metrics

#### Logs (Loki)
1. Go to Explore → Select Loki
2. Query example: `{service_name="greenhouse-app"}`
3. Filter by log level, service, or custom labels

#### Traces (Tempo)
1. Go to Explore → Select Tempo
2. Search traces by service name, duration, or tags
3. Click on a trace to see:
   - Span timeline and relationships
   - Correlated logs (click "Logs for this span")
   - Related metrics

## Configuration

### Environment Variables

The greenhouse app supports these environment variables:

- `OTEL_EXPORTER_OTLP_ENDPOINT` - OTLP collector endpoint (default: http://otel-collector:4317)
- `OTEL_EXPORTER_OTLP_INSECURE` - Use insecure connection (default: true)

### Resource Limits

Each service has CPU and memory limits configured:

| Service | CPU Limit | Memory Limit |
|---------|-----------|--------------|
| OTel Collector | 0.5 | 512MB |
| Prometheus | 1.0 | 1GB |
| Loki | 0.5 | 512MB |
| Tempo | 0.5 | 512MB |
| Grafana | 0.5 | 512MB |
| App | 0.25 | 256MB |

Adjust these in [docker-compose.yml](docker-compose.yml) based on your needs.

### Data Persistence

All data is persisted in Docker volumes:

- `prometheus-data` - Metrics data (retention: configurable)
- `loki-data` - Log data
- `tempo-data` - Trace data (retention: 24h by default)
- `grafana-data` - Dashboards and settings

To reset all data:
```bash
docker-compose down -v
```

## Monitoring Your Own Applications

### Instrumenting Applications

#### Python with OpenTelemetry

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Setup
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)
span_exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(span_exporter))

# Use
with tracer.start_as_current_span("operation_name"):
    # Your code here
    pass
```

#### Metrics Endpoint

Expose Prometheus metrics on any port:

```python
from prometheus_client import start_http_server, Counter

# Start metrics server
start_http_server(8000)

# Define metrics
requests = Counter('my_app_requests_total', 'Total requests')
requests.inc()
```

Then add to [config/prometheus.yml](config/prometheus.yml):

```yaml
- job_name: 'my-app'
  static_configs:
    - targets: ['my-app:8000']
```

## Maintenance

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f grafana
docker-compose logs -f otel-collector
```

### Restarting Services

```bash
# Restart specific service
docker-compose restart grafana

# Restart all
docker-compose restart
```

### Updating Configuration

After modifying config files:

```bash
# Recreate affected services
docker-compose up -d --force-recreate otel-collector

# Or restart all
docker-compose restart
```

### Backup Data

```bash
# Backup volumes
docker run --rm -v monitor_prometheus-data:/data -v $(pwd):/backup ubuntu tar czf /backup/prometheus-backup.tar.gz /data
docker run --rm -v monitor_loki-data:/data -v $(pwd):/backup ubuntu tar czf /backup/loki-backup.tar.gz /data
docker run --rm -v monitor_grafana-data:/data -v $(pwd):/backup ubuntu tar czf /backup/grafana-backup.tar.gz /data
```

## Troubleshooting

### Services Won't Start

Check logs:
```bash
docker-compose logs [service-name]
```

Common issues:
- Port conflicts: Change port mappings in docker-compose.yml
- Insufficient memory: Increase Docker memory limit or reduce service limits
- Config errors: Validate YAML syntax in config files

### No Data in Grafana

1. Check service health: `docker-compose ps`
2. Verify data sources in Grafana → Configuration → Data sources
3. Check if app is sending data: `docker-compose logs greenhouse-app`
4. Verify OTLP collector is receiving data: `docker-compose logs otel-collector`

### High Memory Usage

- Reduce retention periods in Tempo and Prometheus configs
- Lower resource limits in docker-compose.yml
- Reduce scrape intervals in prometheus.yml

## Production Considerations

### Security

- Change default Grafana password immediately
- Enable authentication on Prometheus and other services
- Use TLS certificates (not included in this setup)
- Restrict network access using firewalls

### Scalability

- Consider using remote storage for Prometheus (e.g., Thanos, Cortex)
- Use distributed Loki with object storage
- Deploy Tempo with object storage backend
- Add load balancers for high availability

### Monitoring the Monitors

- Set up alerts in Prometheus for service health
- Monitor disk usage for data volumes
- Set up external health checks

## Additional Resources

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Loki Documentation](https://grafana.com/docs/loki/)
- [Tempo Documentation](https://grafana.com/docs/tempo/)
- [Grafana Documentation](https://grafana.com/docs/grafana/)

## License

This is an example monitoring stack for educational and development purposes.
