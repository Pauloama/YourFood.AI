"""Configuration management for the ABSA pipeline.

Loads YAML configuration files and environment variables.
"""

from __future__ import annotations

import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any


def _project_root() -> Path:
    """Find project root (directory containing pyproject.toml)."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent.parent.parent


PROJECT_ROOT = _project_root()


@dataclass
class ModelConfig:
    """Model configuration."""
    base_model: str = "neuralmind/bert-base-portuguese-cased"
    num_labels: int = 12
    version: str = "bertimbau-aspects-v1"


@dataclass
class DataConfig:
    """Data configuration."""
    input_path: str = "data/splits"
    max_length: int = 128


@dataclass
class TrainingConfig:
    """Training configuration."""
    batch_size: int = 16
    learning_rate: float = 2e-5
    weight_decay: float = 0.01
    epochs: int = 5
    warmup_ratio: float = 0.1
    gradient_accumulation_steps: int = 1
    seed: int = 42
    early_stopping_patience: int = 2
    mixed_precision: bool = True
    output_dir: str = "artifacts"
    save_checkpoints: bool = True
    checkpoint_dir: str = "artifacts/checkpoints"
    log_dir: str = "reports/training"


@dataclass
class MetricsConfig:
    """Metrics configuration."""
    primary: str = "macro_f1"
    threshold_search_min: float = 0.10
    threshold_search_max: float = 0.90


@dataclass
class PipelineConfig:
    """Complete pipeline configuration."""
    model: ModelConfig = field(default_factory=ModelConfig)
    data: DataConfig = field(default_factory=DataConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)


def load_config(path: Path | str) -> PipelineConfig:
    """Load a pipeline configuration from a YAML file.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        PipelineConfig instance.
    """
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f)

    config = PipelineConfig()

    if "model" in data:
        model_data = data["model"]
        config.model = ModelConfig(
            base_model=model_data.get("base_model", config.model.base_model),
            num_labels=model_data.get("num_labels", config.model.num_labels),
            version=model_data.get("version", config.model.version),
        )

    if "data" in data:
        data_section = data["data"]
        config.data = DataConfig(
            input_path=data_section.get("input_path", config.data.input_path),
            max_length=data_section.get("max_length", config.data.max_length),
        )

    if "training" in data:
        t = data["training"]
        config.training = TrainingConfig(
            batch_size=t.get("batch_size", config.training.batch_size),
            learning_rate=t.get("learning_rate", config.training.learning_rate),
            weight_decay=t.get("weight_decay", config.training.weight_decay),
            epochs=t.get("epochs", config.training.epochs),
            warmup_ratio=t.get("warmup_ratio", config.training.warmup_ratio),
            gradient_accumulation_steps=t.get("gradient_accumulation_steps", config.training.gradient_accumulation_steps),
            seed=t.get("seed", config.training.seed),
            early_stopping_patience=t.get("early_stopping_patience", config.training.early_stopping_patience),
            mixed_precision=t.get("mixed_precision", config.training.mixed_precision),
            output_dir=t.get("output_dir", config.training.output_dir),
            save_checkpoints=t.get("save_checkpoints", config.training.save_checkpoints),
            checkpoint_dir=t.get("checkpoint_dir", config.training.checkpoint_dir),
            log_dir=t.get("log_dir", config.training.log_dir),
        )

    if "metrics" in data:
        m = data["metrics"]
        config.metrics = MetricsConfig(
            primary=m.get("primary", config.metrics.primary),
            threshold_search_min=m.get("threshold_search_min", config.metrics.threshold_search_min),
            threshold_search_max=m.get("threshold_search_max", config.metrics.threshold_search_max),
        )

    return config


@dataclass
class APIConfig:
    """API server configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    aspect_detector_path: str = "artifacts/aspect-detector/bertimbau-aspects-v1"
    sentiment_classifier_path: str = "artifacts/sentiment-classifier/bertimbau-aspect-sentiment-v1"
    max_text_length: int = 1024
    max_batch_size: int = 32
    log_level: str = "INFO"
    log_full_text: bool = False
    taxonomy_version: str = "food-reviews-taxonomy-v1"


def load_api_config(path: Path | str | None = None) -> APIConfig:
    """Load API configuration from YAML and environment variables.

    Environment variables override YAML values:
    - MODEL_PATH overrides both model paths (as base directory)
    - LOG_LEVEL overrides log level
    - LOG_FULL_TEXT overrides log_full_text
    - API_HOST overrides host
    - API_PORT overrides port
    - MAX_TEXT_LENGTH overrides max_text_length
    - MAX_BATCH_SIZE overrides max_batch_size
    """
    config = APIConfig()

    if path is not None:
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f)

        if "server" in data:
            config.host = data["server"].get("host", config.host)
            config.port = data["server"].get("port", config.port)
        if "models" in data:
            config.aspect_detector_path = data["models"].get(
                "aspect_detector_path", config.aspect_detector_path
            )
            config.sentiment_classifier_path = data["models"].get(
                "sentiment_classifier_path", config.sentiment_classifier_path
            )
        if "limits" in data:
            config.max_text_length = data["limits"].get("max_text_length", config.max_text_length)
            config.max_batch_size = data["limits"].get("max_batch_size", config.max_batch_size)
        if "logging" in data:
            config.log_level = data["logging"].get("level", config.log_level)
            config.log_full_text = data["logging"].get("log_full_text", config.log_full_text)
        if "versions" in data:
            config.taxonomy_version = data["versions"].get("taxonomy", config.taxonomy_version)

    # Environment variable overrides
    if model_path := os.environ.get("MODEL_PATH"):
        config.aspect_detector_path = f"{model_path}/aspect-detector/bertimbau-aspects-v1"
        config.sentiment_classifier_path = f"{model_path}/sentiment-classifier/bertimbau-aspect-sentiment-v1"
    if log_level := os.environ.get("LOG_LEVEL"):
        config.log_level = log_level
    if log_full_text := os.environ.get("LOG_FULL_TEXT"):
        config.log_full_text = log_full_text.lower() in ("true", "1", "yes")
    if api_host := os.environ.get("API_HOST"):
        config.host = api_host
    if api_port := os.environ.get("API_PORT"):
        config.port = int(api_port)
    if max_text := os.environ.get("MAX_TEXT_LENGTH"):
        config.max_text_length = int(max_text)
    if max_batch := os.environ.get("MAX_BATCH_SIZE"):
        config.max_batch_size = int(max_batch)

    return config
