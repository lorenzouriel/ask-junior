# Weaviate Vector Database
A Docker-based setup for running Weaviate, an open-source vector database designed for AI applications, semantic search, and machine learning workflows.

## Overview
This project provides a production-ready Weaviate instance with:
- OpenAI text vectorization capabilities
- API key authentication
- Persistent data storage
- Backup functionality
- Prometheus monitoring
- Optimized resource configuration

## Quick Start
1. Start the Weaviate service:
```bash
docker-compose up -d
```

2. Verify the service is running:
```bash
docker ps
```

3. Access the API at `http://localhost:8081`

## Configuration
### Ports
- **8081**: HTTP API endpoint
- **50051**: gRPC API endpoint
- **2112**: Prometheus metrics endpoint

### Authentication
API key authentication is enabled with two keys:
- `readonlykey`: Read-only access
- `adminkey`: Administrative access

**Example usage:**
```bash
curl -H "Authorization: Bearer adminkey" http://localhost:8081/v1/schema
```

### Modules
The following modules are enabled:
- **text2vec-openai**: OpenAI-based text vectorization (default)
- **backup-filesystem**: File system backup support
- **qna-openai**: Question-answering with OpenAI

### Resource Limits
Current configuration:
- **CPU cores**: 4 (GOMAXPROCS)
- **Memory limit**: 6GiB

Adjust these values in the docker-compose.yml based on your system resources.

### Data Persistence
- **Data volume**: `weaviate_data` (Docker volume)
- **Backup directory**: `./include/weaviate/backup` (host mount)

## Monitoring
Prometheus monitoring is enabled and exposed on port 2112. Access metrics at:
```
http://localhost:2112/metrics
```

## Backup
Backups are stored in `./weaviate/backup` on the host machine. Ensure this directory exists before starting the service:
```bash
mkdir -p ./weaviate/backup
```

## Common Operations

### View logs
```bash
docker-compose logs -f weaviate
```

### Stop the service
```bash
docker-compose down
```

### Stop and remove data
```bash
docker-compose down -v
```

### Restart the service
```bash
docker-compose restart
```