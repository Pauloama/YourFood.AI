#!/usr/bin/env python3
"""Train the multi-label aspect detector (Model 1).

Usage:
    python scripts/train_aspect_detector.py --config configs/train_aspects.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import yaml
from transformers import AutoTokenizer

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from absa.config import load_config
from absa.datasets import compute_file_hash, load_data, records_to_reviews
from absa.logging_config import get_logger, setup_logging
from absa.models.aspect_detector import (
    AspectDetectionDataset,
    AspectDetector,
    compute_pos_weights,
    train_aspect_detector,
)
from absa.taxonomy import load_taxonomy

logger = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Train Aspect Detector (Model 1)")
    parser.add_argument(
        "--config", "-c",
        required=True,
        help="Path to training config YAML",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        return 1

    setup_logging(level="INFO")
    cfg = load_config(config_path)
    taxonomy = load_taxonomy()

    logger.info("training_aspect_detector_init", config=str(config_path))

    data_dir = Path(cfg.data.input_path)
    train_path = data_dir / "train_aggregated.jsonl"
    val_path = data_dir / "val_aggregated.jsonl"

    if not train_path.exists():
        # Fallback to train.jsonl
        train_path = data_dir / "train.jsonl"
    if not val_path.exists():
        val_path = data_dir / "val.jsonl"

    if not train_path.exists() or not val_path.exists():
        print(f"Error: Split files not found in {data_dir}", file=sys.stderr)
        return 1

    # Load data
    train_records = load_data(train_path)
    val_records = load_data(val_path)

    # Convert to reviews
    train_reviews = records_to_reviews(train_records)
    val_reviews = records_to_reviews(val_records)

    train_texts = [r.text for r in train_reviews]
    val_texts = [r.text for r in val_reviews]

    train_labels = np.array([r.to_multilabel_vector(taxonomy) for r in train_reviews])
    val_labels = np.array([r.to_multilabel_vector(taxonomy) for r in val_reviews])

    # Compute pos_weight from training set only
    pos_weights = compute_pos_weights(train_labels)

    tokenizer = AutoTokenizer.from_pretrained(cfg.model.base_model)
    detector = AspectDetector(
        base_model_name=cfg.model.base_model,
        num_labels=cfg.model.num_labels,
        pos_weight=pos_weights,
    )

    train_dataset = AspectDetectionDataset(
        texts=train_texts,
        labels=train_labels,
        tokenizer=tokenizer,
        max_length=cfg.data.max_length,
    )
    val_dataset = AspectDetectionDataset(
        texts=val_texts,
        labels=val_labels,
        tokenizer=tokenizer,
        max_length=cfg.data.max_length,
    )

    output_dir = Path(cfg.training.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = train_aspect_detector(
        model=detector,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        val_dataset=val_dataset,
        output_dir=output_dir,
        epochs=cfg.training.epochs,
        batch_size=cfg.training.batch_size,
        learning_rate=cfg.training.learning_rate,
        weight_decay=cfg.training.weight_decay,
        warmup_ratio=cfg.training.warmup_ratio,
        gradient_accumulation_steps=cfg.training.gradient_accumulation_steps,
        early_stopping_patience=cfg.training.early_stopping_patience,
        mixed_precision=cfg.training.mixed_precision,
        seed=cfg.training.seed,
        taxonomy=taxonomy,
    )

    # Save metadata & config
    with open(output_dir / "labels.json", "w", encoding="utf-8") as f:
        json.dump(taxonomy.aspect_codes, f, indent=2)

    with open(output_dir / "taxonomy.json", "w", encoding="utf-8") as f:
        json.dump({
            "version": taxonomy.version,
            "aspects": taxonomy.aspect_codes,
            "entities": taxonomy.entity_mapping,
        }, f, indent=2)

    with open(output_dir / "training_config.yaml", "w", encoding="utf-8") as f:
        with open(config_path, "r", encoding="utf-8") as rf:
            f.write(rf.read())

    metadata = {
        "model_type": "AspectDetector",
        "version": cfg.model.version,
        "base_model": cfg.model.base_model,
        "timestamp": datetime.now().isoformat(),
        "train_file_hash": compute_file_hash(train_path),
        "best_val_macro_f1": result["best_val_macro_f1"],
    }
    with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info("training_aspect_detector_complete", best_f1=result["best_val_macro_f1"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
