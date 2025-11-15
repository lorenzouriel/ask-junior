"""
Observability module for OpenTelemetry integration with traces, logs, and metrics.
Connects to existing OpenTelemetry Collector stack.
"""
import os
import logging
from typing import Optional, Dict, Any
from functools import wraps
import time

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor


class ObservabilityManager:
    """Manages OpenTelemetry instrumentation for traces, logs, and metrics."""

    def __init__(
        self,
        service_name: str = "ask-junior-agent",
        otel_endpoint: str = "http://localhost:4317",
        environment: str = "development"
    ):
        self.service_name = service_name
        self.otel_endpoint = otel_endpoint
        self.environment = environment

        # Create resource with service information
        self.resource = Resource.create({
            "service.name": service_name,
            "service.version": "1.0.0",
            "deployment.environment": environment,
        })

        # Initialize components
        self.tracer_provider = None
        self.meter_provider = None
        self.logger_provider = None
        self.tracer = None
        self.meter = None
        self.logger = None

        # Metrics instruments
        self.request_counter = None
        self.request_duration = None
        self.error_counter = None
        self.chunk_counter = None
        self.token_counter = None

    def setup_tracing(self):
        """Setup distributed tracing with OTLP exporter."""
        # Create tracer provider
        self.tracer_provider = TracerProvider(resource=self.resource)

        # Create OTLP span exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=self.otel_endpoint,
            insecure=True  # Use insecure for local development
        )

        # Add span processor
        span_processor = BatchSpanProcessor(otlp_exporter)
        self.tracer_provider.add_span_processor(span_processor)

        # Set global tracer provider
        trace.set_tracer_provider(self.tracer_provider)

        # Get tracer
        self.tracer = trace.get_tracer(__name__)

        return self.tracer

    def setup_metrics(self):
        """Setup metrics collection with OTLP exporter."""
        # Create OTLP metric exporter
        otlp_exporter = OTLPMetricExporter(
            endpoint=self.otel_endpoint,
            insecure=True
        )

        # Create metric reader with shorter export interval for testing
        metric_reader = PeriodicExportingMetricReader(
            otlp_exporter,
            export_interval_millis=5000  # Export every 5 seconds (reduced for faster visibility)
        )

        # Create meter provider
        self.meter_provider = MeterProvider(
            resource=self.resource,
            metric_readers=[metric_reader]
        )

        # Set global meter provider
        metrics.set_meter_provider(self.meter_provider)

        # Get meter
        self.meter = metrics.get_meter(__name__)

        # Store exporter for manual flush
        self.metric_exporter = otlp_exporter

        # Create metric instruments
        self.request_counter = self.meter.create_counter(
            name="agent.requests.total",
            description="Total number of requests processed",
            unit="1"
        )

        self.request_duration = self.meter.create_histogram(
            name="agent.request.duration",
            description="Request duration in seconds",
            unit="s"
        )

        self.error_counter = self.meter.create_counter(
            name="agent.errors.total",
            description="Total number of errors",
            unit="1"
        )

        self.chunk_counter = self.meter.create_counter(
            name="agent.chunks.retrieved",
            description="Number of chunks retrieved from vector DB",
            unit="1"
        )

        self.token_counter = self.meter.create_counter(
            name="agent.tokens.used",
            description="Number of tokens used in LLM calls",
            unit="1"
        )

        return self.meter

    def setup_logging(self, log_level: str = "INFO"):
        """Setup logging with OTLP exporter."""
        # Create OTLP log exporter
        otlp_exporter = OTLPLogExporter(
            endpoint=self.otel_endpoint,
            insecure=True
        )

        # Create logger provider
        self.logger_provider = LoggerProvider(resource=self.resource)

        # Add log processor
        log_processor = BatchLogRecordProcessor(otlp_exporter)
        self.logger_provider.add_log_record_processor(log_processor)

        # Set global logger provider
        set_logger_provider(self.logger_provider)

        # Setup standard logging
        logging.basicConfig(level=getattr(logging, log_level.upper()))
        self.logger = logging.getLogger(self.service_name)

        # Attach OTLP handler to logger
        handler = LoggingHandler(
            level=getattr(logging, log_level.upper()),
            logger_provider=self.logger_provider
        )
        self.logger.addHandler(handler)

        # Instrument logging
        LoggingInstrumentor().instrument(set_logging_format=True)

        return self.logger

    def initialize(self, log_level: str = "INFO"):
        """Initialize all observability components."""
        self.setup_tracing()
        self.setup_metrics()
        self.setup_logging(log_level)

        self.logger.info(
            f"Observability initialized for {self.service_name}",
            extra={
                "environment": self.environment,
                "otel_endpoint": self.otel_endpoint
            }
        )

    def trace_operation(self, operation_name: str, attributes: Optional[Dict[str, Any]] = None):
        """Decorator to trace synchronous operations."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Filter attributes to only include primitive types
                filtered_attrs = {}
                if attributes:
                    for key, value in attributes.items():
                        if isinstance(value, (str, int, float, bool)):
                            filtered_attrs[key] = value
                        elif value is None:
                            filtered_attrs[key] = "None"
                        else:
                            filtered_attrs[key] = str(value)

                with self.tracer.start_as_current_span(
                    operation_name,
                    attributes=filtered_attrs
                ) as span:
                    start_time = time.time()
                    try:
                        result = func(*args, **kwargs)
                        duration = time.time() - start_time

                        # Record metrics (filter None values)
                        metric_attrs = {"operation": operation_name, "status": "success"}
                        self.request_duration.record(duration, metric_attrs)
                        self.request_counter.add(1, metric_attrs)

                        span.set_attribute("duration_seconds", duration)
                        span.set_attribute("status", "success")

                        return result

                    except Exception as e:
                        duration = time.time() - start_time

                        # Record error metrics
                        error_attrs = {
                            "operation": operation_name,
                            "error_type": type(e).__name__
                        }
                        self.error_counter.add(1, error_attrs)
                        self.request_duration.record(
                            duration,
                            {"operation": operation_name, "status": "error"}
                        )

                        span.set_attribute("error", True)
                        span.set_attribute("error.type", type(e).__name__)
                        span.set_attribute("error.message", str(e))
                        span.record_exception(e)

                        self.logger.error(
                            f"Error in {operation_name}: {str(e)}",
                            exc_info=True,
                            extra={"operation": operation_name}
                        )

                        raise

            return wrapper
        return decorator

    def trace_async_operation(self, operation_name: str, attributes: Optional[Dict[str, Any]] = None):
        """Decorator to trace async operations."""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Filter attributes to only include primitive types
                filtered_attrs = {}
                if attributes:
                    for key, value in attributes.items():
                        if isinstance(value, (str, int, float, bool)):
                            filtered_attrs[key] = value
                        elif value is None:
                            filtered_attrs[key] = "None"
                        else:
                            filtered_attrs[key] = str(value)

                with self.tracer.start_as_current_span(
                    operation_name,
                    attributes=filtered_attrs
                ) as span:
                    start_time = time.time()
                    try:
                        result = await func(*args, **kwargs)
                        duration = time.time() - start_time

                        # Record metrics
                        metric_attrs = {"operation": operation_name, "status": "success"}
                        self.request_duration.record(duration, metric_attrs)
                        self.request_counter.add(1, metric_attrs)

                        span.set_attribute("duration_seconds", duration)
                        span.set_attribute("status", "success")

                        return result

                    except Exception as e:
                        duration = time.time() - start_time

                        # Record error metrics
                        error_attrs = {
                            "operation": operation_name,
                            "error_type": type(e).__name__
                        }
                        self.error_counter.add(1, error_attrs)
                        self.request_duration.record(
                            duration,
                            {"operation": operation_name, "status": "error"}
                        )

                        span.set_attribute("error", True)
                        span.set_attribute("error.type", type(e).__name__)
                        span.set_attribute("error.message", str(e))
                        span.record_exception(e)

                        self.logger.error(
                            f"Error in {operation_name}: {str(e)}",
                            exc_info=True,
                            extra={"operation": operation_name}
                        )

                        raise

            return wrapper
        return decorator

    def force_flush(self):
        """Force flush all pending telemetry data."""
        try:
            if self.tracer_provider:
                self.tracer_provider.force_flush()
            if self.meter_provider:
                self.meter_provider.force_flush()
            if self.logger_provider:
                self.logger_provider.force_flush()
        except Exception as e:
            print(f"Error flushing telemetry: {e}")

    def shutdown(self):
        """Shutdown all observability components gracefully."""
        # Force flush before shutdown
        self.force_flush()

        if self.tracer_provider:
            self.tracer_provider.shutdown()
        if self.meter_provider:
            self.meter_provider.shutdown()
        if self.logger_provider:
            self.logger_provider.shutdown()


# Global observability manager instance
observability_manager = ObservabilityManager(
    otel_endpoint=os.getenv("OTEL_ENDPOINT", "http://localhost:4317")
)
