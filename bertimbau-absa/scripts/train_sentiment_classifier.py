#!/usr/bin/env python3
"""Train the aspect-conditioned sentiment classifier (Model 2).

Usage:
    python scripts/train_sentiment_classifier.py --config configs/train_sentiment.yaml
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
from absa.datasets import compute_file_hash, load_data
from absa.logging_config import get_logger, setup_logging
from absa.models.sentiment_classifier import (
    SentimentClassifier,
    SentimentDataset,
    compute_class_weights,
    train_sentiment_classifier,
)
from absa.taxonomy import load_taxonomy

logger = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Train Sentiment Classifier (Model 2)")
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

    logger.info("training_sentiment_classifier_init", config=str(config_path))

    data_dir = Path(cfg.data.input_path)
    train_path = data_dir / "train.jsonl"
    val_path = data_dir / "val.jsonl"

    if not train_path.exists() or not val_path.exists():
        print(f"Error: Split files not found in {data_dir}", file=sys.stderr)
        return 1

    train_records = load_data(train_path)
    val_records = load_data(val_path)

    # Filter rows with aspect and sentiment
    def _extract_pairs(records: list[dict]) -> tuple[list[str], list[str], list[int]]:
        texts, aspects, labels = [], [], []
        for r in records:
            asp = r.get("aspect")
            sent = r.get("sentiment")
            txt = r.get("text")
            if asp and sent and txt and taxonomy.is_valid_aspect(str(asp)) and taxonomy.is_valid_sentiment(str(sent)):
                texts.append(str(txt))
                aspects.append(str(asp))
                labels.append(taxonomy.sentiment_to_index(str(sent)))
        return texts, aspects, labels

    train_texts, train_aspects, train_labels = _extract_pairs(train_records)
    val_texts, val_aspects, val_labels = _extract_pairs(val_records)

    if not train_texts or not val_texts:
        print("Error: No valid annotated samples found for training/validation.", file=sys.stderr)
        return 1

    class_weights = compute_class_weights(train_labels, num_classes=taxonomy.num_sentiments)

    tokenizer = AutoTokenizer.from_pretrained(cfg.model.base_model)
    classifier = SentimentClassifier(
        base_model_name=cfg.model.base_model,
        num_labels=cfg.model.num_labels,
        class_weights=class_weights,
    )

    train_dataset = SentimentDataset(
        texts=train_texts,
        aspects=train_aspects,
        labels=train_labels,
        tokenizer=tokenizer,
        max_length=cfg.data.max_length,
    )
    val_dataset = SentimentDataset(
        texts=val_texts,
        aspects=val_aspects,
        labels=val_labels,
        tokenizer=tokenizer,
        max_length=cfg.data.max_length,
    )

    output_dir = Path(cfg.training.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = train_sentiment_classifier(
        model=classifier,
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

    with open(output_dir / "labels.json", "w", encoding="utf-8") as f:
        json.dump(list(taxonomy.sentiments), f, indent=2)

    with open(output_dir / "taxonomy.json", "w", encoding="utf-8") as f:
        json.dump({
            "version": taxonomy.version,
            "sentiments": list(taxonomy.sentiments),
            "aspects": taxonomy.aspect_codes,
        }, f, indent=2)

    with open(output_dir / "training_config.yaml", "w", encoding="utf-8") as f:
        with open(config_path, "r", encoding="utf-8") as rf:
            f.write(rf.read())

    metadata = {
        "model_type": "SentimentClassifier",
        "version": cfg.model.version,
        "base_model": cfg.model.base_model,
        "timestamp": datetime.now().isoformat(),
        "train_file_hash": compute_file_hash(train_path),
        "best_val_macro_f1": result["best_val_macro_f1"],
    }
    with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info("training_sentiment_classifier_complete", best_f1=result["best_val_macro_f1"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
