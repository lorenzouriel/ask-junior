# Tempo Config Documentation

## `server`

```yaml
server:
  http_listen_port: 3200
```

| Field                    | Meaning                                                                                                 |
| ------------------------ | ------------------------------------------------------------------------------------------------------- |
| `http_listen_port: 3200` | Tempo's **HTTP API and UI** will be accessible on port **3200** (e.g., `/api/search`, `/status`, etc.). |

## `distributor` — Incoming Trace Data

```yaml
distributor:
  receivers:
    otlp:
      protocols:
        grpc:
        http:
```

This defines **how Tempo receives trace data**.

| Protocol  | Default port | Use case                                           |
| --------- | ------------ | -------------------------------------------------- |
| gRPC      | 4317         | Standard/efficient tracing ingestion (recommended) |
| HTTP/JSON | 4318         | Alternative for clients that don't support gRPC    |

This allows sending traces from **OpenTelemetry SDKs, agents, or OTEL Collector** to Tempo — via OTLP **gRPC or HTTP**.

## `compactor` — Retention & Block Management

```yaml
compactor:
  compaction:
    block_retention: 24h
```

| Key                    | Meaning                                                                                     |
| ---------------------- | ------------------------------------------------------------------------------------------- |
| `block_retention: 24h` | Tempo will **keep traces only for 24 hours**, then automatically delete older trace blocks. |

Useful for **low-cost local setups**, short-lived demos, or testing environments.

For production, values like `7d`, `30d`, or `90d` are more common.

## `storage.trace` — Storage Settings

```yaml
storage:
  trace:
    backend: local
    local:
      path: /tmp/tempo/traces
```

| Field                     | Description                                                               |
| ------------------------- | ------------------------------------------------------------------------- |
| `backend: local`          | Trace data will be stored **locally on disk** (not in S3, GCS, or MinIO). |
| `path: /tmp/tempo/traces` | Filesystem location where Tempo writes its trace blocks.                  |

### What gets stored here?

This path contains:

* Raw trace blocks (compressed)
* Index files
* Logically grouped trace data that can be queried by Tempo

## Full Flow (Simplified)

| Function                     | Component                       |
| ---------------------------- | ------------------------------- |
| Sends trace data             | Apps → OpenTelemetry SDK        |
| Pushes trace data to         | Tempo (OTLP gRPC or HTTP)       |
| Tempo writes trace blocks to | `/tmp/tempo/traces`             |
| Queries traces from Grafana  | via Tempo HTTP API on port 3200 |
| Retains data for             | 24 hours                        |
