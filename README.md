# Ask Junior

[![GitHub stars](https://img.shields.io/github/stars/lorenzouriel/ask-junior?style=social)](https://github.com/lorenzouriel/ask-junior/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/lorenzouriel/ask-junior?style=social)](https://github.com/lorenzouriel/ask-junior/network/members)
[![GitHub issues](https://img.shields.io/github/issues/lorenzouriel/ask-junior)](https://github.com/lorenzouriel/ask-junior/issues)
[![GitHub release](https://img.shields.io/github/v/release/lorenzouriel/ask-junior)](https://github.com/lorenzouriel/ask-junior/releases)

A production-ready RAG (Retrieval-Augmented Generation) system that provides an intelligent conversational AI interface with full observability, automated knowledge base ingestion, and enterprise-grade infrastructure.

## Architecture Overview

Ask Junior is built as a microservices architecture with five core services that work together to deliver an end-to-end AI-powered knowledge assistant.
```bash
                    --------------------
                    |  External Data   |
                    |  Sources         |
                    |  - Azure DevOps  |
                    |  - Local Files   |
                    ---------,----------
                             |
                             |
              --------------------------------
              |      INTEGRATIONS            |
              |      (Apache Airflow)        |
              |      Port: 8080              |
              |                              |
              |    Document extraction       |
              |    Smart chunking            |
              |    Vectorization pipeline    |
              |    Scheduled syncs           |
              ---------------,----------------
                             |
                             |
              --------------------------------
              |    VECTOR DATABASE           |
              |    (Weaviate)                |
              |    Port: 8081                |
              |                              |
              |    Semantic search           |
              |    OpenAI embeddings         |
              |    API key auth              |
              ---------------,----------------
                             |
                             |
              --------------------------------
              |        AGENT                 |
              |        (Chainlit)            |
              |        Port: 8000            |
              |                              |
              |    Chat interface            |
              |    RAG retrieval             |
              |    OpenAI GPT-4              |
              |    Conversation memory       |
              ---------------,----------------
                             |
         --------------------<--------------------
         |                   |                   |
         |                   |                   |
    -----------      ----------------    ----------------
    |  User   |      |   OpenAI     |    |   MONITOR    |
    |Response |      |   API        |    |  (Grafana,   |
    -----------      ----------------    |  Prometheus, |
                                         |  Loki, Tempo)|
                                         |  Port: 3000  |
                                         ----------------
                                                |
                                                |
                            --------------------------------
                            |         TRAEFIK              |
                            |    (Reverse Proxy)           |
                            |    Port: 80, 443             |
                            |                              |
                            |  Routes all services via     |
                            |  *.local hostnames           |
                            --------------------------------
```

## Services

| Service | Description | Port | Technology |
|---------|-------------|------|------------|
| [agent/](agent/) | Conversational AI chat interface with RAG | 8000 | Chainlit, OpenAI |
| [monitor/](monitor/) | Full observability stack | 3000 | Grafana, Prometheus, Loki, Tempo |
| [integrations/](integrations/) | ETL & RAG pipeline for document processing | 8080 | Apache Airflow |
| [traefik/](traefik/) | Reverse proxy and load balancer | 80/443 | Traefik v3.0 |
| [vector_database/](vector_database/) | Semantic search engine | 8081 | Weaviate |

## Data Flow

1. **Knowledge Ingestion**: Documents from Azure DevOps or local files are processed by Airflow
2. **Vectorization**: Documents are chunked, embedded via OpenAI, and stored in Weaviate
3. **User Query**: User asks a question through the Chainlit interface
4. **Semantic Search**: Weaviate retrieves relevant document chunks
5. **Response Generation**: OpenAI GPT-4 generates a response using retrieved context
6. **Observability**: All operations are traced, logged, and metrified

## Quick Start

### Prerequisites

- Docker and Docker Compose
- OpenAI API key
- 16GB RAM minimum
- 4 CPU cores recommended

### 1. Clone the Repository

```bash
git clone https://github.com/lorenzouriel/ask-junior.git
cd ask-junior
```

### 2. Start Services (Use the guide inside each service)

Start services in the following order:

```bash
# 1. Vector Database (required first)
cd vector_database && docker compose up -d --build

# 2. Monitoring Stack
cd ../monitor && docker compose up -d --build

# 3. Integrations (Airflow)
cd ../integrations && docker compose up -d --build

# 4. Agent
cd ../agent && docker compose up -d --build

# 5. Traefik (optional, for routing)
cd ../traefik && docker compose up -d --build
```

### 3. Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| Agent Chat | http://localhost:8000 or http://agent.local | - |
| Airflow | http://localhost:8080 or http://airflow.local | admin / admin |
| Grafana | http://localhost:3000 or http://grafana.local | admin / admin |
| Prometheus | http://localhost:9090 | - |
| Weaviate | http://localhost:8081 | API Key: `adminkey` |
| Traefik Dashboard | http://localhost:8888 | - |

## Network Architecture

Each service creates its own Docker network, with Traefik connecting to all of them:

```bash
--------------------------------------------------------------
|  Docker Host                                               |
|                                                            |
|  ---------------------  ---------------------              |
|  | ask-junior-network|  | airflow-network   |              |
|  | -- agent          |  | -- postgres       |              |
|  ---------------------  | -- redis          |              |
|                         | -- scheduler      |              |
|  ---------------------  | -- worker         |              |
|  | monitoring        |  ---------------------              |
|  | -- otel-collector |                                     |
|  | -- prometheus     |  ---------------------              |
|  | -- loki           |  | weaviate          |              |
|  | -- tempo          |  | -- weaviate       |              |
|  | -- grafana        |  ---------------------              |
|  ---------------------                                     |
|                         ---------------------              |
|                         | traefik-network   |              |
|                         | -- traefik        ||- connects   |
|                         ---------------------    to all    |
--------------------------------------------------------------
```

## Service Details

### Agent (Chainlit)

The conversational interface that implements RAG:

- **Features**: Adjustable chunk retrieval (1-20), certainty thresholds, conversation memory
- **Observability**: Full OpenTelemetry integration (traces, logs, metrics)
- **Storage**: SQLite for conversation history and analytics

### Monitor (Observability Stack)

Complete three-pillars observability:

| Component | Purpose | Port |
|-----------|---------|------|
| OpenTelemetry Collector | Central telemetry hub | 4317/4318 |
| Prometheus | Metrics storage | 9090 |
| Loki | Log aggregation | 3100 |
| Tempo | Distributed tracing | 3200 |
| Grafana | Unified visualization | 3000 |

### Integrations (Apache Airflow)

ETL pipelines for knowledge base management:

**DAGs**:
- `weaviate_rag_kb_azuredevops_extract`: Syncs from Azure DevOps every 3 hours
- `weaviate_rag_kb_ingest`: Processes and ingests documents every 4 hours

**Supported Formats**: Markdown, PDF, TXT

**Chunking Strategy**:
- Markdown: Header-aware splitting preserving structure
- Others: Recursive character splitting (1000 chars, 200 overlap)

### Vector Database (Weaviate)

Semantic search engine with OpenAI embeddings:

- **Modules**: text2vec-openai, backup-filesystem, qna-openai
- **Auth**: API key-based (readonlykey, adminkey)
- **Resources**: 4 CPU cores, 6GB memory limit

### Traefik (Reverse Proxy)

Cloud-native reverse proxy:

- Host-based routing for all services
- Automatic service discovery via Docker
- Dashboard on port 8888

## Next Steps

- [ ] Configure proper secrets management (not .env files)
- [ ] Set up TLS certificates in Traefik
- [ ] Configure Grafana with proper authentication
- [ ] Set up backup retention for Weaviate
- [ ] Configure Airflow for production (separate DB, workers)
- [ ] Set resource limits appropriate for workload
- [ ] Configure alerting in Prometheus/Grafana

## Ports Summary

| Port | Service | Protocol |
|------|---------|----------|
| 80 | Traefik HTTP | HTTP |
| 443 | Traefik HTTPS | HTTPS |
| 3000 | Grafana | HTTP |
| 3100 | Loki | HTTP |
| 3200 | Tempo | HTTP |
| 4317 | OTel Collector | gRPC |
| 4318 | OTel Collector | HTTP |
| 8000 | Agent | HTTP |
| 8080 | Airflow | HTTP |
| 8081 | Weaviate | HTTP |
| 8888 | Traefik Dashboard | HTTP |
| 9090 | Prometheus | HTTP |
| 50051 | Weaviate | gRPC |

## Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with `docker compose up --build`
5. Submit a pull request

## License
MIT License

## Support
- Issues: https://github.com/lorenzouriel/ask-junior/issues
- Documentation: See individual service README files