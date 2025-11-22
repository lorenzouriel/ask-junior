# Otel Config Documentation

## `receivers`

Receivers define **how the OpenTelemetry Collector receives telemetry data** (logs, metrics, traces).

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
```

### `otlp receiver`

The OTLP receiver accepts **logs, traces, and metrics** in the OpenTelemetry Protocol format.

| Protocol | Port | Use case                                                     |
| -------- | ---- | ------------------------------------------------------------ |
| gRPC     | 4317 | Default, efficient, interoperable with most SDKs (preferred) |
| HTTP     | 4318 | Alternative for environments where gRPC is restrictive       |

➡ `0.0.0.0` makes it listen on **all network interfaces**.

### `prometheus receiver`

```yaml
prometheus:
  config:
    scrape_configs:
      - job_name: 'otel-collector'
        static_configs:
          - targets: ['localhost:9464']
```

* Makes the Collector act **like Prometheus**, scraping metrics from the target.
* It scrapes metrics from **localhost:9464** — which could be:

  * The Collector's own Prometheus exporter
  * Another service exposing metrics in Prometheus format

## `exporters`

Exporters send telemetry data to external systems.

```yaml
exporters:
  loki:
    endpoint: "http://loki:3100/loki/api/v1/push"
    tls:
      insecure: true
```

### Loki exporter (for logs)

| Field                | Meaning                                                  |
| -------------------- | -------------------------------------------------------- |
| `endpoint`           | Loki API endpoint to push logs                           |
| `tls.insecure: true` | Allows HTTP/non-TLS — fine for local/dev, not production |

```yaml
  otlp/trace:
    endpoint: "tempo:4317"
    tls:
      insecure: true
```

### OTLP Trace exporter → Tempo

* Sends **traces** to **Grafana Tempo** over gRPC at port 4317.
* `insecure: true` → uses HTTP/no TLS (development-friendly)

```yaml
  prometheus:
    endpoint: "0.0.0.0:9464"
```

### Prometheus exporter

* Exposes **metrics for scraping** at `http://<host>:9464/metrics`.
* Used by Prometheus or even Loki dashboard monitoring.

```yaml
  logging:
    loglevel: debug
```

### Logging exporter

* Prints telemetry data to Collector's console/logs.
* Useful for debugging pipelines (shows payloads, verifies processing).

## `service.pipelines`

Defines how telemetry flows: **Receiver → Processor (optional) → Exporter**

```yaml
service:
  pipelines:
    logs:
      receivers: [otlp]
      exporters: [loki, logging]

    traces:
      receivers: [otlp]
      exporters: [otlp/trace, logging]

    metrics:
      receivers: [otlp]
      exporters: [prometheus]
```

### Logs Pipeline

| Receives from   | Exports to                                          |
| --------------- | --------------------------------------------------- |
| OTLP (app logs) | Loki (for storage & querying) + Logging (debugging) |

### Traces Pipeline

| Receives from             | Exports to                                  |
| ------------------------- | ------------------------------------------- |
| OTLP (tracing SDKs/agent) | Tempo (trace storage) + Logging (debugging) |

### Metrics Pipeline

| Receives from                      | Exports to                          |
| ---------------------------------- | ----------------------------------- |
| OTLP (SDKs or Prometheus receiver) | Prometheus exporter (scraped later) |

## Summary

| Telemetry Type | Source                    | Destination                   |
| -------------- | ------------------------- | ----------------------------- |
| Logs           | OTLP (gRPC/HTTP)          | Loki                          |
| Traces         | OTLP                      | Tempo                         |
| Metrics        | OTLP or Prometheus scrape | Prometheus endpoint (scraped) |
