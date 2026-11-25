"""FastAPI application entry point for ABSA service."""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config import load_api_config
from ..inference import ABSAPipeline
from ..logging_config import get_logger, setup_logging
from ..taxonomy import get_taxonomy
from .dependencies import get_api_config, set_pipeline
from .routes import router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager: loads models on startup once."""
    config = get_api_config()
    setup_logging(level=config.log_level, log_full_text=config.log_full_text)
    taxonomy = get_taxonomy()

    aspect_path = Path(config.aspect_detector_path)
    sentiment_path = Path(config.sentiment_classifier_path)

    logger.info(
        "app_startup_loading_models",
        aspect_path=str(aspect_path),
        sentiment_path=str(sentiment_path),
    )

    if aspect_path.exists() and sentiment_path.exists():
        try:
            pipeline = ABSAPipeline.from_artifacts(
                aspect_detector_dir=aspect_path,
                sentiment_classifier_dir=sentiment_path,
                taxonomy=taxonomy,
            )
            set_pipeline(pipeline)
            logger.info("models_loaded_successfully")
        except Exception as e:
            logger.error("failed_to_load_models_on_startup", error=str(e))
            set_pipeline(None)
    else:
        logger.warning(
            "model_artifacts_not_found_startup",
            msg="API started without models loaded. Returning 503 until models exist.",
        )
        set_pipeline(None)

    yield

    logger.info("app_shutdown")
    set_pipeline(None)


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="BERTimbau ABSA API",
        description="Aspect-Based Sentiment Analysis for Food Reviews in Brazilian Portuguese",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        corr_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = corr_id
        start_time = time.perf_counter()

        response: Response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        response.headers["X-Correlation-ID"] = corr_id
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
        return response

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An internal server error occurred.",
                "correlationId": getattr(request.state, "correlation_id", "unknown"),
            },
        )

    app.include_router(router)
    return app


app = create_app()
