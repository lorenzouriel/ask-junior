# Greenhouse Monitoring Test Application

A Python application that demonstrates OpenTelemetry integration with metrics, logs, and distributed tracing using Prometheus, Loki, and Tempo.

## Overview

The [app.py](app.py) application is a test service that showcases observability best practices by generating:

- **Metrics**: Request counters exposed via Prometheus format
- **Logs**: Structured logging at multiple levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Traces**: Distributed tracing spans with attributes and events

The application simulates processing 10 requests with a 2-second interval between each, making it ideal for testing and visualizing telemetry data in Grafana.

## Architecture

The app integrates with the monitoring stack defined in [docker-compose.yml](../docker-compose.yml):

- **OpenTelemetry Collector**: Receives telemetry data via OTLP (gRPC on port 4317)
- **Prometheus**: Scrapes and stores metrics
- **Loki**: Stores and queries logs
- **Tempo**: Stores and queries distributed traces
- **Grafana**: Visualizes all telemetry data

## Requirements

- Python 3.11+
- Dependencies listed in [requirements.txt](requirements.txt)

## Installation

### Using pip

```bash
pip install -r requirements.txt
```

### Using uv (recommended)

```bash
uv sync
```

## Running the Application

### 1. Start the Monitoring Stack

From the parent directory, start all monitoring services:

```bash
cd ..
docker-compose up -d
```

This will start:
- OpenTelemetry Collector on ports 4317 (gRPC) and 4318 (HTTP)
- Prometheus on port 9090
- Loki on port 3100
- Tempo on port 3200
- Grafana on port 3000

### 2. Run the Test Application

From the test directory:

```bash
python app.py
```

Or with uv:

```bash
uv run app.py
```

The application will:
- Start a Prometheus metrics server on port 8000
- Process 10 simulated requests with 2-second intervals
- Send logs to the OpenTelemetry Collector
- Send traces to Tempo
- Expose metrics for Prometheus to scrape

## Configuration

The application uses the following environment variable:

- `OTEL_EXPORTER_OTLP_ENDPOINT`: OpenTelemetry Collector endpoint (default: `http://localhost:4317`)

To use a different endpoint:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://custom-host:4317
python app.py
```

## Viewing Telemetry Data

Once the application is running, access Grafana to visualize the data:

1. Open [http://localhost:3000](http://localhost:3000) in your browser
2. Login with credentials: `admin` / `admin`
3. Navigate to:
   - **Explore > Prometheus**: View metrics (`app_requests_total`)
   - **Explore > Loki**: Query logs from the `greenhouse-app` service
   - **Explore > Tempo**: Visualize distributed traces and spans