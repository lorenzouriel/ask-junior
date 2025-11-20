import logging
import os
import time
from prometheus_client import start_http_server, Counter
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.metrics import set_meter_provider
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Get OTLP endpoint from environment variable
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

# Set up OpenTelemetry Tracing with Tempo
trace.set_tracer_provider(
    TracerProvider(resource=Resource.create({"service.name": "greenhouse-app"}))
)
tracer = trace.get_tracer_provider().get_tracer(__name__)
span_exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True)
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(span_exporter))

# Set up OpenTelemetry Logging
logger_provider = LoggerProvider(
    resource=Resource.create(
        {
            "service.name": "greenhouse-app",
            "service.instance.id": "instance-1",
        }
    ),
)
set_logger_provider(logger_provider)
log_exporter = OTLPLogExporter(insecure=True)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
logging.getLogger().addHandler(handler)
logging.basicConfig(level=logging.NOTSET)

# Set up OpenTelemetry Metrics with Prometheus
reader = PrometheusMetricReader()
meter_provider = MeterProvider(resource=Resource.create({"service.name": "greenhouse-app"}), metric_readers=[reader])
set_meter_provider(meter_provider)
meter = meter_provider.get_meter("greenhouse-app")

# Define Prometheus metrics
request_counter = Counter("app_requests_total", "Total number of requests received")

# Start Prometheus metrics server
start_http_server(8000)  # Exposes metrics on http://localhost:8000

# Logging, tracing, and metric simulation
for i in range(10):
    with tracer.start_as_current_span("process_request") as span:
        request_counter.inc()
        logging.info(f"Processing request {i + 1}")

        # Example log messages
        logging.debug("This is a debug message. It provides detailed information for debugging purposes.")
        logging.info("This is an info message. It confirms that things are working as expected.")
        logging.warning("This is a warning message. It indicates a potential issue that might need attention.")
        logging.error("This is an error message. It indicates a serious problem that has occurred.")
        logging.critical("This is a critical message. It indicates a severe issue that could lead to failure.")

        span.set_attribute("request.number", i + 1)
        span.add_event("Request processed")

    time.sleep(2)