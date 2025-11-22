# Ask Junior Agent
A conversational AI agent built with Chainlit, featuring RAG (Retrieval-Augmented Generation) using Weaviate vector database, complete observability with OpenTelemetry, and conversation memory with SQLite.

## Features
- **Conversational Interface**: Built with Chainlit for a modern chat experience
- **RAG Pipeline**: Retrieves relevant context from Weaviate vector database
- **LLM Integration**: Uses OpenAI GPT-4 for intelligent responses
- **Full Observability**:
  - Distributed tracing with OpenTelemetry
  - Structured logging to Loki
  - Metrics collection to Prometheus
  - Visualization with Grafana via Tempo
- **Conversation Memory**: SQLite-based storage for conversation history and analytics
- **Configurable Settings**: Adjustable chunk retrieval and certainty thresholds

## Architecture
```
User Query → Chainlit UI → Weaviate (Vector Search) → OpenAI GPT-4 → Response
                ↓
          Observability Stack
          - Traces → Tempo
          - Logs → Loki
          - Metrics → Prometheus
                ↓
            Grafana (Visualization)
                ↓
          SQLite (Memory & Analytics)
```

## Prerequisites
- Python 3.9+
- Docker (for observability stack)
- Weaviate instance running
- OpenAI API key

## Installation
1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and configure:
```bash
cp .env.example .env
```

3. Update .env with your configuration

## Running the Agent

### Start Observability Stack (if not already running)
```bash
cd ../monitor
docker-compose up -d
```

This starts:
- **OpenTelemetry Collector** (ports 4317/4318)
- **Tempo** (port 3200) - Distributed tracing
- **Loki** (port 3100) - Log aggregation
- **Prometheus** (port 9090) - Metrics
- **Grafana** (port 3000) - Visualization dashboard

### Start the Agent
```bash
chainlit run app.py

# Or

docker compose up -d
```

The agent will be available at http://localhost:8000

## Observability

### Viewing Traces, Logs, and Metrics

1. Open Grafana: http://localhost:3000
   - Default credentials: admin/admin

2. Explore data sources:
   - **Tempo** for distributed traces
   - **Loki** for logs
   - **Prometheus** for metrics

### Key Metrics Tracked

- agent.requests.total - Total number of requests
- agent.request.duration - Request duration histogram
- agent.errors.total - Total errors by type
- agent.chunks.retrieved - Number of chunks retrieved from vector DB
- agent.tokens.used - LLM token usage

### Traces

All operations are traced:
- handle_message - End-to-end message processing
- weaviate_retrieval - Vector database queries
- llm_inference - OpenAI API calls

## Memory Management

### SQLite Database Schema

The agent stores conversation data in SQLite with the following tables:

1. **sessions** - Chat sessions
2. **messages** - Individual messages (user/assistant)
3. **interactions** - Query-answer pairs with retrieval metadata
4. **metrics** - Custom metrics per session

## Configuration

### Adjustable Settings (via UI)

- **Number of chunks**: 1-20 (default: 5)
- **Certainty threshold**: 0.0-1.0 (default: 0.75)

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| WEAVIATE_CLASS_NAME | Weaviate collection name | Required |
| WEAVIATE_URL | Weaviate instance URL | Required |
| WEAVIATE_AUTH | Weaviate API key | Required |
| OPENAI_API_KEY | OpenAI API key | Required |
| OTEL_ENDPOINT | OpenTelemetry collector endpoint | http://localhost:4317 |
| LOG_LEVEL | Logging level | INFO |
| MEMORY_DB_PATH | SQLite database path | agent_memory.db |
