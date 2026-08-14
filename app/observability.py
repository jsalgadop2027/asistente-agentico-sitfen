"""Observabilidad: logging estructurado + activación de LangSmith (AIOps).

Sigue prácticas SRE/AIOps: logs estructurados JSON en Cloud Run (los recoge
Cloud Logging automáticamente) y trazas de la cadena agéntica en LangSmith.
"""
from __future__ import annotations

import logging
import os
import sys

import structlog

from app.config import get_secret, settings

_CONFIGURED = False


def configure_observability() -> None:
    """Configura logging estructurado y variables de LangSmith. Idempotente."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # LangSmith: resolver API key desde Secret Manager si no está en entorno.
    if settings.langchain_tracing_v2:
        api_key = settings.langchain_api_key or get_secret(
            settings.secret_langsmith_api_key, fallback_env="LANGCHAIN_API_KEY"
        )
        if api_key:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = api_key
            os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
            # Privacidad: oculta inputs/outputs en las trazas para que la PII del
            # mensaje del usuario no quede registrada en LangSmith (minimización).
            if settings.langsmith_hide_io:
                for var in ("LANGCHAIN_HIDE_INPUTS", "LANGCHAIN_HIDE_OUTPUTS",
                            "LANGSMITH_HIDE_INPUTS", "LANGSMITH_HIDE_OUTPUTS"):
                    os.environ[var] = "true"
        else:
            get_logger(__name__).warning("langsmith_key_missing")

    # Confident AI: observabilidad de producción (DeepEval tracing). Best-effort;
    # si falla, no debe impedir el arranque del servicio.
    try:
        from app.confident_tracing import configure as _configure_confident

        _configure_confident()
    except Exception as exc:  # noqa: BLE001
        get_logger(__name__).warning("confident_setup_failed", error=str(exc))

    _CONFIGURED = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
