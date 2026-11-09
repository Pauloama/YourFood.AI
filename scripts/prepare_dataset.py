#!/usr/bin/env python3
"""Prepare and normalize a dataset for the ABSA pipeline.

Applies text normalization, detects conflicts, flags reviews for
review, and outputs normalized and aggregated JSONL files.

Usage:
    python scripts/prepare_dataset.py --input data/raw/reviews.jsonl --output data/processed
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from absa.datasets import (
    compute_file_hash,
    detect_conflicts,
    load_data,
    records_to_reviews,
    reviews_to_aggregated_jsonl,
    reviews_to_normalized_jsonl,
)
from absa.preprocessing import normalize_text
from absa.taxonomy import load_taxonomy


def prepare_dataset(
    input_path: Path,
    output_dir: Path,
    taxonomy_path: str | None = None,
) -> dict:
    """Prepare a dataset for training.

    Steps:
    1. Load raw data
    2. Normalize text
    3. Convert to ReviewRecord objects
    4. Detect and flag conflicts
    5. Exclude flagged reviews from training set
    6. Write normalized and aggregated output files
    7. Generate preparation manifest

    Args:
        input_path: Path to raw data file.
        output_dir: Output directory.
        taxonomy_path: Optional path to taxonomy YAML.

    Returns:
        Preparation manifest dictionary.
    """
    taxonomy = load_taxonomy(taxonomy_path)

    print(f"Loading data from {input_path}...")
    records = load_data(input_path)
    print(f"Loaded {len(records)} records")

    # Normalize text
    for rec in records:
        if "text" in rec and rec["text"]:
            rec["text"] = normalize_text(str(rec["text"]))

    # Convert to ReviewRecord objects
    reviews = records_to_reviews(records)
    print(f"Found {len(reviews)} unique reviews")

    # Detect conflicts
    conflicts = detect_conflicts(reviews)
    conflict_ids = {c["review_id"] for c in conflicts}

    # Flag conflicting reviews
    for review in reviews:
        if review.review_id in conflict_ids:
            review.requires_review = True

    # Split into trainable and flagged
    trainable_reviews = [r for r in reviews if not r.requires_review]
    flagged_reviews = [r for r in reviews if r.requires_review]

    print(f"Trainable reviews: {len(trainable_reviews)}")
    print(f"Flagged for review: {len(flagged_reviews)}")

    # Write outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    # Normalized (one row per aspect occurrence) - trainable only
    norm_path = reviews_to_normalized_jsonl(
        trainable_reviews, output_dir / "reviews.jsonl"
    )
    print(f"Normalized trainable data written to {norm_path}")

    # Aggregated (one row per review) - trainable only
    agg_path = reviews_to_aggregated_jsonl(
        trainable_reviews, output_dir / "reviews_aggregated.jsonl"
    )
    print(f"Aggregated trainable data written to {agg_path}")

    # Flagged reviews (for human review)
    if flagged_reviews:
        flagged_path = reviews_to_normalized_jsonl(
            flagged_reviews, output_dir / "reviews_flagged.jsonl"
        )
        print(f"Flagged reviews written to {flagged_path}")

    # All reviews aggregated (including flagged, for reference)
    all_agg_path = reviews_to_aggregated_jsonl(
        reviews, output_dir / "reviews_all_aggregated.jsonl"
    )

    # Generate manifest
    manifest = {
        "input_file": str(input_path),
        "input_hash": compute_file_hash(input_path),
        "taxonomy_version": taxonomy.version,
        "total_reviews": len(reviews),
        "trainable_reviews": len(trainable_reviews),
        "flagged_reviews": len(flagged_reviews),
        "conflicts_detected": len(conflicts),
        "conflict_details": conflicts,
        "output_files": {
            "normalized": str(norm_path),
            "normalized_hash": compute_file_hash(norm_path),
            "aggregated": str(agg_path),
            "aggregated_hash": compute_file_hash(agg_path),
        },
        "reviews_with_aspects": sum(1 for r in trainable_reviews if r.has_aspects),
        "reviews_without_aspects": sum(1 for r in trainable_reviews if not r.has_aspects),
    }

    manifest_path = output_dir / "preparation_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"Manifest written to {manifest_path}")

    return manifest


def main() -> int:
    """Main entry point."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    parser = argparse.ArgumentParser(
        description="Prepare and normalize dataset for ABSA pipeline",
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to input data file (.jsonl or .csv)",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output directory for processed data",
    )
    parser.add_argument(
        "--taxonomy",
        default=None,
        help="Path to taxonomy YAML (default: configs/taxonomy.yaml)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        manifest = prepare_dataset(input_path, output_dir, args.taxonomy)
        print(f"\n✅ Dataset prepared successfully.")
        print(f"Trainable reviews: {manifest['trainable_reviews']}")
        print(f"Flagged for review: {manifest['flagged_reviews']}")
        return 0
    except Exception as e:
        print(f"\n❌ Error preparing dataset: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
