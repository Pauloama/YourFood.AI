#!/usr/bin/env python3
"""Evaluate integrated ABSA pipeline on test split.

Usage:
    python scripts/evaluate_pipeline.py --input data/splits/test.jsonl --output reports/final
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from absa.config import load_api_config
from absa.datasets import load_data, records_to_reviews
from absa.inference import ABSAPipeline
from absa.logging_config import get_logger, setup_logging
from absa.metrics import PipelinePrediction, compute_pipeline_metrics, save_metrics_report
from absa.taxonomy import load_taxonomy

logger = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Integrated ABSA Pipeline")
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to test dataset (e.g. data/splits/test.jsonl or test_aggregated.jsonl)",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Directory to save evaluation reports",
    )
    parser.add_argument(
        "--aspect-model",
        default=None,
        help="Path to aspect detector artifact",
    )
    parser.add_argument(
        "--sentiment-model",
        default=None,
        help="Path to sentiment classifier artifact",
    )
    args = parser.parse_args()

    setup_logging(level="INFO")
    taxonomy = load_taxonomy()
    api_cfg = load_api_config()

    aspect_dir = args.aspect_model or api_cfg.aspect_detector_path
    sentiment_dir = args.sentiment_model or api_cfg.sentiment_classifier_path

    logger.info(
        "pipeline_evaluation_init",
        aspect_model=aspect_dir,
        sentiment_model=sentiment_dir,
        input_file=args.input,
    )

    try:
        pipeline = ABSAPipeline.from_artifacts(
            aspect_detector_dir=aspect_dir,
            sentiment_classifier_dir=sentiment_dir,
            taxonomy=taxonomy,
        )
    except Exception as e:
        print(f"Error loading models: {e}", file=sys.stderr)
        return 1

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1

    records = load_data(input_path)
    reviews = records_to_reviews(records)
    print(f"Loaded {len(reviews)} unique reviews for evaluation.")

    predictions: list[PipelinePrediction] = []

    for rev in reviews:
        res = pipeline.analyze_review(review_id=rev.review_id, text=rev.text)

        pred_pairs = [(a.aspect, a.sentiment) for a in res.aspects]
        true_pairs = [(ann.aspect, ann.sentiment) for ann in rev.annotations]

        predictions.append(
            PipelinePrediction(
                review_id=rev.review_id,
                predicted_pairs=pred_pairs,
                true_pairs=true_pairs,
                latency_ms=res.processing_time_ms,
                num_aspects_predicted=len(pred_pairs),
            )
        )

    metrics = compute_pipeline_metrics(predictions=predictions, taxonomy=taxonomy)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, md_path = save_metrics_report(
        metrics=metrics,
        output_dir=out_dir,
        filename_prefix="integrated_pipeline_evaluation",
    )

    print("\n=== Integrated Pipeline Evaluation ===")
    print(f"Exact pair precision: {metrics['pair_metrics']['precision']}")
    print(f"Exact pair recall:    {metrics['pair_metrics']['recall']}")
    print(f"Exact pair F1:        {metrics['pair_metrics']['f1']}")
    print(f"Fully correct reviews: {metrics['fully_correct_rate']:.1%}")
    print(f"Latency p50:          {metrics['latency']['p50_ms']} ms")
    print(f"Latency p95:          {metrics['latency']['p95_ms']} ms")
    print(f"\nReports saved to:")
    print(f" - {json_path}")
    print(f" - {md_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
