"""OpenTelemetry (traces) + logs JSON structurés corrélés par trace_id."""
import json
import logging
import os
import sys
from datetime import datetime, timezone

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


class JsonFormatter(logging.Formatter):
    """Un log = une ligne JSON, avec trace_id/span_id du span courant."""

    def format(self, record: logging.LogRecord) -> str:
        ctx = trace.get_current_span().get_span_context()
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": os.getenv("OTEL_SERVICE_NAME", "payment-api"),
            "trace_id": format(ctx.trace_id, "032x") if ctx.is_valid else None,
            "span_id": format(ctx.span_id, "016x") if ctx.is_valid else None,
        }
        payload.update(getattr(record, "fields", {}))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging() -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO"))
    return logging.getLogger("payment-api")


def setup_telemetry(app) -> None:
    """Exporte les traces en OTLP/HTTP si OTEL_EXPORTER_OTLP_ENDPOINT est défini."""
    resource = Resource.create(
        {"service.name": os.getenv("OTEL_SERVICE_NAME", "payment-api")}
    )
    provider = TracerProvider(resource=resource)
    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, excluded_urls="metrics,health")
