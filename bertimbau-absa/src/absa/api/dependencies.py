"""Dependency injection and state management for FastAPI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status

from ..config import APIConfig, load_api_config
from ..inference import ABSAPipeline
from ..logging_config import get_logger

logger = get_logger(__name__)

_pipeline_instance: Optional[ABSAPipeline] = None
_api_config: Optional[APIConfig] = None


def get_api_config() -> APIConfig:
    """Get loaded API configuration."""
    global _api_config
    if _api_config is None:
        cfg_path = Path(__file__).parent.parent.parent.parent / "configs" / "api.yaml"
        _api_config = load_api_config(cfg_path if cfg_path.exists() else None)
    return _api_config


def set_pipeline(pipeline: Optional[ABSAPipeline]) -> None:
    """Set active pipeline instance."""
    global _pipeline_instance
    _pipeline_instance = pipeline


def get_pipeline() -> ABSAPipeline:
    """Dependency that returns the loaded ABSAPipeline or raises 503."""
    global _pipeline_instance
    if _pipeline_instance is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ABSA models are not currently loaded or available.",
        )
    return _pipeline_instance


def is_aspect_model_loaded() -> bool:
    return _pipeline_instance is not None and _pipeline_instance.aspect_detector is not None


def is_sentiment_model_loaded() -> bool:
    return _pipeline_instance is not None and _pipeline_instance.sentiment_classifier is not None
