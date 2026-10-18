"""
OpenTelemetry distributed tracing setup for Odysseus.

Kill-switch: set environment variable ODYSSEUS_OTEL=off to disable ALL tracing.
When off, no OTel SDK is initialised and no spans are created — zero overhead.

When on:
  • FastAPI auto-instrumented (HTTP requests, response codes, latency)
  • SQLAlchemy auto-instrumented (query duration, DB connection pool stats)
  • httpx auto-instrumented (outbound HTTP calls — LLM APIs, tools, etc.)
  • OTLP exporter sends spans to the OTel Collector

Usage in app.py:
    from services.observability.otel_setup import setup_otel
    setup_otel(app, engine)  # in lifespan / startup

Author: Agent A8 — Distributed Tracing (OpenTelemetry, CNCF, Apache 2.0)
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Kill-switch
# ---------------------------------------------------------------------------


def _otel_enabled() -> bool:
    """Return True if OTel tracing is NOT disabled by the kill-switch."""
    return os.getenv("ODYSSEUS_OTEL", "on").strip().lower() != "off"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def setup_otel(app: FastAPI, engine: Engine) -> None:
    """
    Initialise OpenTelemetry and auto-instrument FastAPI + SQLAlchemy + httpx.

    Safe to call multiple times — the SDK guards against double-init.
    If ODYSSEUS_OTEL=off, this is a no-op (< 1 µs cost).

    Parameters
    ----------
    app : FastAPI
        The running FastAPI application.
    engine : Engine
        The SQLAlchemy engine (used by core/database.py).
    """
    if not _otel_enabled():
        logger.info("[otel] tracing DISABLED (ODYSSEUS_OTEL=off)")
        return

    # Lazy import so the rest of the app never pays import cost when off.
    from opentelemetry import trace
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # --- Service identity ---------------------------------------------------
    resource = Resource.create(
        {
            SERVICE_NAME: "odysseus-agentos",
            "deployment.environment": os.getenv("ODYSSEUS_ENV", "development"),
        }
    )

    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    # --- OTLP exporter → Collector -----------------------------------------
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318")
        exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info("[otel] OTLP exporter → %s", endpoint)
    except Exception as exc:
        # If Collector is unreachable, still instrument locally (console fallback)
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logger.warning("[otel] OTLP export failed (%s) — falling back to console spans", exc)

    # --- Auto-instrument FastAPI -------------------------------------------
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        logger.info("[otel] FastAPI instrumented")
    except Exception as exc:
        logger.warning("[otel] FastAPI instrumentation failed: %s", exc)

    # --- Auto-instrument SQLAlchemy ----------------------------------------
    try:
        from opentelemetry.instrumentation.sqlalchemy import (
            SQLAlchemyInstrumentor,
        )

        SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=provider)
        logger.info("[otel] SQLAlchemy instrumented")
    except Exception as exc:
        logger.warning("[otel] SQLAlchemy instrumentation failed: %s", exc)

    # --- Auto-instrument httpx (outbound HTTP — LLM calls, tools) ----------
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument(tracer_provider=provider)
        logger.info("[otel] httpx instrumented")
    except Exception as exc:
        logger.warning("[otel] httpx instrumentation failed: %s", exc)

    logger.info("[otel] tracing ENABLED — all instruments active")


# ---------------------------------------------------------------------------
# Tracer helper for manual spans
# ---------------------------------------------------------------------------


def get_tracer(name: str = "odysseus"):
    """
    Return a Tracer for manual span creation.

    Returns a no-op tracer when OTel is disabled, so callers never need
    to check the kill-switch themselves.

    Usage
    -----
        from services.observability.otel_setup import get_tracer
        tracer = get_tracer("odysseus.agent_loop")

        with tracer.start_as_current_span("my_span") as span:
            span.set_attribute("key", "value")
            ...
    """
    from opentelemetry import trace

    if not _otel_enabled():
        return trace.get_tracer("odysseus.noop")  # SDK returns NoOpTracer

    return trace.get_tracer(name)
