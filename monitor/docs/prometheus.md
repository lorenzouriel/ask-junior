# Prometheus Config Documentation

## `global`

```yaml
global:
  scrape_interval: 15s  # Scrape every 15 seconds
```

Defines global settings for Prometheus behavior.

| Setting                | Meaning                                                                                                            |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `scrape_interval: 15s` | Prometheus will scrape (collect) metrics from all defined targets **every 15 seconds**, unless overridden per job. |

## `scrape_configs`

This section defines **jobs**, each tells Prometheus *what to scrape* and *where to scrape it from*.

### Job: OpenTelemetry Collector

```yaml
- job_name: 'otel-collector'
  static_configs:
    - targets: ['otel-collector:9464']
```

| Field                              | Description                                                                                                    |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `job_name: otel-collector`         | Logical name for this scrape job (used in Prometheus UI & labels).                                             |
| `targets: ['otel-collector:9464']` | Prometheus scrapes metrics from the OTEL Collector’s Prometheus exporter endpoint, usually exposed on `:9464`. |

Provides performance metrics of the **OpenTelemetry Collector** itself (CPU, latency, queue depth, dropped telemetry, etc.).

### Job: Loki

```yaml
- job_name: 'loki'
  static_configs:
    - targets: ['loki:3100']
```

| Field                    | Description                                            |
| ------------------------ | ------------------------------------------------------ |
| `job_name: loki`         | Job name shown in Prometheus dashboards and alerts     |
| `targets: ['loki:3100']` | Scrapes from Loki's `/metrics` endpoint (on port 3100) |

Metrics include query performance, ingestion rates, request errors, chunk flush activity, etc.

### Job: Greenhouse App (your application)

```yaml
- job_name: 'greenhouse-app'
  static_configs:
    - targets: ['greenhouse-app:8000']
```

| Field                              | Description                                                                    |
| ---------------------------------- | ------------------------------------------------------------------------------ |
| `job_name: greenhouse-app`         | Custom name for your application’s monitoring job                              |
| `targets: ['greenhouse-app:8000']` | Prometheus scrapes your app’s metrics endpoint (e.g., `/metrics` on port 8000) |

Typically collected via:

* OpenTelemetry metrics SDK
* Prometheus client library (Python, Go, Java, Node.js, etc.)
* Or exported via OTEL Collector to `/metrics`

## Overall Flow of Metrics

| Source                  | Metrics Type                                    | Scraped By |
| ----------------------- | ----------------------------------------------- | ---------- |
| OpenTelemetry Collector | Collector processing, CPU, dropped telemetry    | Prometheus |
| Loki                    | Log ingestion/query metrics                     | Prometheus |
| Greenhouse App          | Application metrics (latency, errors, requests) | Prometheus |

## Usage Tips

You can visualize this in **Grafana** by adding Prometheus as a data source.

Common useful dashboards:

| Component      | Recommended Dashboard                                |
| -------------- | ---------------------------------------------------- |
| OTEL Collector | `OpenTelemetry Operations`                           |
| Loki           | `Loki Overview`                                      |
| App Metrics    | Custom (HTTP latency, requests, CPU, memory, errors) |
