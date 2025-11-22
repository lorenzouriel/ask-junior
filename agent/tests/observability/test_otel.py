"""
Test script to verify OpenTelemetry connection to collector.
Run this to test if traces and metrics are being sent properly.
"""
import os
import time
from dotenv import load_dotenv
from observability import ObservabilityManager

load_dotenv()

# Create observability manager
otel_manager = ObservabilityManager(
    service_name="test-otel-connection",
    otel_endpoint=os.getenv("OTEL_ENDPOINT", "http://localhost:4317")
)

# Initialize
print(f"Initializing OpenTelemetry with endpoint: {otel_manager.otel_endpoint}")
otel_manager.initialize()

print("=" * 60)
print("Testing Logging...")
print("=" * 60)
otel_manager.logger.info("Test log message 1")
otel_manager.logger.warning("Test warning message")
otel_manager.logger.error("Test error message")

print("\n" + "=" * 60)
print("Testing Traces...")
print("=" * 60)

# Test trace
with otel_manager.tracer.start_as_current_span("test_span") as span:
    span.set_attribute("test.attribute", "test_value")
    span.set_attribute("test.number", 42)
    otel_manager.logger.info("Inside test span")
    time.sleep(0.5)
    print("Created test span")

print("\n" + "=" * 60)
print("Testing Metrics...")
print("=" * 60)

# Test metrics
otel_manager.request_counter.add(1, {"test": "metric", "status": "success"})
otel_manager.request_duration.record(1.5, {"test": "metric", "operation": "test"})
otel_manager.chunk_counter.add(5, {"test": "chunks"})
otel_manager.token_counter.add(100, {"model": "test-model"})
print("Recorded test metrics")

print("\n" + "=" * 60)
print("Flushing data...")
print("=" * 60)

# Force flush
otel_manager.force_flush()
time.sleep(2)  # Wait for export

print("\n" + "=" * 60)
print("Shutting down...")
print("=" * 60)

# Shutdown
otel_manager.shutdown()

print("\n" + "=" * 60)
print("Test complete!")
print("=" * 60)
print("\nCheck Grafana at http://localhost:3000")
print("- Tempo: Search for service 'test-otel-connection'")
print("- Prometheus: Query for 'agent_requests_total'")
print("- Loki: Filter by service_name='test-otel-connection'")
