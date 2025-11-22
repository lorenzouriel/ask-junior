# Loki Config Documentation

## `auth_enabled: false`

Disables authentication.
Loki will not require credentials to access its endpoints.
➡ Useful in local or development environments, but unsafe in production.

## `server`

Configures the network interfaces for Loki.

```yaml
server:
  http_listen_port: 3100
  grpc_listen_port: 9096
```

* **http_listen_port: 3100** → Port for HTTP API endpoints (e.g., querying logs, metrics, ingestion).
* **grpc_listen_port: 9096** → Port for gRPC communication (used internally by Loki components and some clients like Promtail or the Distributor).

## `common`

Defines shared settings used across Loki components.

```yaml
common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory
```

### Main parts:

| Setting                               | Explanation                                                                           |
| ------------------------------------- | ------------------------------------------------------------------------------------- |
| `path_prefix: /loki`                  | Base directory for storing data and internal metadata.                                |
| `storage.filesystem.chunks_directory` | Where incoming log chunks are stored on disk.                                         |
| `storage.filesystem.rules_directory`  | Where alerting/recording rules are stored.                                            |
| `replication_factor: 1`               | Only one copy of data (no HA). Suitable for single-node setup.                        |
| `ring.instance_addr: 127.0.0.1`       | Address used for ring communication between components.                               |
| `kvstore.store: inmemory`             | Uses in-memory key-value store for ring data. Good for local/testing, not HA-capable. |

> The **ring** is how Loki tracks instances responsible for handling writes and queries.

## `query_range`

Configures caching for query results.

```yaml
query_range:
  results_cache:
    cache:
      embedded_cache:
        enabled: true
        max_size_mb: 100
```

* **embedded_cache** → Enables in-memory caching directly inside Loki.
* **max_size_mb: 100** → Up to 100 MB of memory allocated to store cached query results.

> Improves query performance by reusing results from previous identical queries.

## `schema_config`

Controls how Loki stores and indexes logs.

```yaml
schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h
```

| Setting                    | Purpose                                                                             |
| -------------------------- | ----------------------------------------------------------------------------------- |
| `from`                     | When this schema becomes active.                                                    |
| `store: boltdb-shipper`    | Uses BoltDB index files with the “shipper” model (supports local or cloud storage). |
| `object_store: filesystem` | Stores index and logs on local filesystem.                                          |
| `schema: v11`              | Current TSDB-compatible schema version.                                             |
| `index.prefix`             | Prefix used for index files (e.g., index_20241120).                                 |
| `index.period: 24h`        | Creates a new index file every 24 hours (daily index).                              |

## `ruler`

Settings for alerting and rule evaluations.

```yaml
ruler:
  alertmanager_url: http://localhost:9093
```

* **alertmanager_url** → URL where Loki will send alert notifications (typically Prometheus Alertmanager).

## `limits_config`

Controls ingestion rules and system limits.

```yaml
limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 168h
  ingestion_rate_mb: 16
  ingestion_burst_size_mb: 32
```

| Setting                            | Explanation                                               |
| ---------------------------------- | --------------------------------------------------------- |
| `reject_old_samples: true`         | Rejects logs that are too old (prevents backdated logs).  |
| `reject_old_samples_max_age: 168h` | Maximum allowed age is 168 hours (7 days).                |
| `ingestion_rate_mb: 16`            | Soft limit: average ingestion rate limit (MB per second). |
| `ingestion_burst_size_mb: 32`      | Hard limit: max burst size allowed for ingestion spikes.  |

## Summary
This configuration sets up **Loki 2.9.5** for a **single-node, filesystem-based deployment** with:
- Local storage
- BoltDB-shipper indexing
- Query caching
- Basic rate limiting
- Alerting integration with Alertmanager
- No authentication