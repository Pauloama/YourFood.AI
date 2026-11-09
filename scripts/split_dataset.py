#!/usr/bin/env python3
"""Split dataset into train/validation/test partitions.

Ensures no review_id leaks across partitions.
Supports grouping by user_id, order_id, or review_id.
Supports temporal split when created_at is available.

Usage:
    python scripts/split_dataset.py --input data/processed/reviews.jsonl --output data/splits --seed 42
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from absa.datasets import (
    ReviewRecord,
    compute_file_hash,
    load_data,
    records_to_reviews,
    reviews_to_normalized_jsonl,
    reviews_to_aggregated_jsonl,
)
from absa.taxonomy import load_taxonomy


def _get_group_key(review: ReviewRecord, strategy: str) -> str:
    """Get the grouping key for a review based on strategy."""
    if strategy == "user_id" and review.user_id:
        return review.user_id
    elif strategy == "order_id" and review.order_id:
        return review.order_id
    return review.review_id


def _detect_split_strategy(reviews: list[ReviewRecord]) -> str:
    """Detect the best split strategy based on available fields.

    Priority: user_id > order_id > review_id
    """
    has_user_id = any(r.user_id for r in reviews)
    has_order_id = any(r.order_id for r in reviews)

    if has_user_id:
        return "user_id"
    elif has_order_id:
        return "order_id"
    else:
        return "review_id"


def split_by_group(
    reviews: list[ReviewRecord],
    strategy: str,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> tuple[list[ReviewRecord], list[ReviewRecord], list[ReviewRecord]]:
    """Split reviews into train/val/test by group.

    Ensures all records with the same review_id stay in the same partition.

    Args:
        reviews: All review records.
        strategy: Grouping strategy (user_id, order_id, review_id).
        train_ratio: Training set ratio.
        val_ratio: Validation set ratio.
        test_ratio: Test set ratio.
        seed: Random seed.

    Returns:
        Tuple of (train, val, test) review lists.
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6

    # Group reviews by key
    groups: dict[str, list[ReviewRecord]] = defaultdict(list)
    for review in reviews:
        key = _get_group_key(review, strategy)
        groups[key].append(review)

    # Shuffle group keys
    rng = np.random.RandomState(seed)
    group_keys = sorted(groups.keys())
    rng.shuffle(group_keys)

    n = len(group_keys)
    train_end = int(n * train_ratio)
    val_end = train_end + int(n * val_ratio)

    train_keys = set(group_keys[:train_end])
    val_keys = set(group_keys[train_end:val_end])
    test_keys = set(group_keys[val_end:])

    train_reviews: list[ReviewRecord] = []
    val_reviews: list[ReviewRecord] = []
    test_reviews: list[ReviewRecord] = []

    for key, group_reviews in groups.items():
        if key in train_keys:
            train_reviews.extend(group_reviews)
        elif key in val_keys:
            val_reviews.extend(group_reviews)
        else:
            test_reviews.extend(group_reviews)

    return train_reviews, val_reviews, test_reviews


def split_temporal(
    reviews: list[ReviewRecord],
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> tuple[list[ReviewRecord], list[ReviewRecord], list[ReviewRecord]]:
    """Split reviews temporally using created_at field.

    Oldest reviews go to train, middle to validation, newest to test.

    Args:
        reviews: Reviews with created_at field.
        train_ratio: Training set ratio.
        val_ratio: Validation set ratio.

    Returns:
        Tuple of (train, val, test) review lists.

    Raises:
        ValueError: If not enough reviews have created_at.
    """
    # Filter reviews with timestamps and sort
    timed = [(r, r.created_at) for r in reviews if r.created_at]
    if len(timed) < len(reviews) * 0.5:
        raise ValueError(
            f"Only {len(timed)}/{len(reviews)} reviews have created_at. "
            f"Need at least 50% for temporal split."
        )

    timed.sort(key=lambda x: x[1])

    n = len(timed)
    train_end = int(n * train_ratio)
    val_end = train_end + int(n * val_ratio)

    train = [r for r, _ in timed[:train_end]]
    val = [r for r, _ in timed[train_end:val_end]]
    test = [r for r, _ in timed[val_end:]]

    # Add reviews without timestamps to training
    untimed = [r for r in reviews if not r.created_at]
    train.extend(untimed)

    return train, val, test


def compute_split_stats(
    reviews: list[ReviewRecord],
    taxonomy=None,
) -> dict:
    """Compute statistics for a split partition."""
    if taxonomy is None:
        taxonomy = load_taxonomy()

    aspect_counts: Counter = Counter()
    sentiment_counts: Counter = Counter()

    for review in reviews:
        for ann in review.annotations:
            aspect_counts[ann.aspect] += 1
            sentiment_counts[ann.sentiment] += 1

    return {
        "num_reviews": len(reviews),
        "num_annotations": sum(aspect_counts.values()),
        "reviews_with_aspects": sum(1 for r in reviews if r.has_aspects),
        "reviews_without_aspects": sum(1 for r in reviews if not r.has_aspects),
        "aspect_distribution": dict(aspect_counts.most_common()),
        "sentiment_distribution": dict(sentiment_counts.most_common()),
    }


def check_leakage(
    train: list[ReviewRecord],
    val: list[ReviewRecord],
    test: list[ReviewRecord],
) -> list[str]:
    """Check for review_id leakage across partitions."""
    train_ids = {r.review_id for r in train}
    val_ids = {r.review_id for r in val}
    test_ids = {r.review_id for r in test}

    leaks: list[str] = []
    tv = train_ids & val_ids
    tt = train_ids & test_ids
    vt = val_ids & test_ids

    if tv:
        leaks.append(f"Train-Val overlap: {len(tv)} review_ids ({list(tv)[:5]})")
    if tt:
        leaks.append(f"Train-Test overlap: {len(tt)} review_ids ({list(tt)[:5]})")
    if vt:
        leaks.append(f"Val-Test overlap: {len(vt)} review_ids ({list(vt)[:5]})")

    return leaks


def main() -> int:
    """Main entry point."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    parser = argparse.ArgumentParser(
        description="Split dataset into train/validation/test partitions",
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to processed data file (.jsonl)",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output directory for splits",
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--strategy",
        choices=["user_id", "order_id", "review_id", "auto", "temporal"],
        default="auto",
        help="Split strategy (default: auto-detect)",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.70,
        help="Training set ratio (default: 0.70)",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.15,
        help="Validation set ratio (default: 0.15)",
    )
    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.15,
        help="Test set ratio (default: 0.15)",
    )
    parser.add_argument(
        "--taxonomy",
        default=None,
        help="Path to taxonomy YAML",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1

    # Validate ratios
    total_ratio = args.train_ratio + args.val_ratio + args.test_ratio
    if abs(total_ratio - 1.0) > 1e-6:
        print(f"Error: Ratios must sum to 1.0, got {total_ratio}", file=sys.stderr)
        return 1

    taxonomy = load_taxonomy(args.taxonomy)

    # Load data
    print(f"Loading data from {input_path}...")
    records = load_data(input_path)
    reviews = records_to_reviews(records)
    print(f"Loaded {len(reviews)} reviews")

    # Determine strategy
    strategy = args.strategy
    if strategy == "auto":
        strategy = _detect_split_strategy(reviews)
        print(f"Auto-detected split strategy: {strategy}")
    elif strategy == "temporal":
        print("Using temporal split strategy")

    # Split
    if strategy == "temporal":
        train, val, test = split_temporal(
            reviews, args.train_ratio, args.val_ratio
        )
    else:
        train, val, test = split_by_group(
            reviews, strategy,
            args.train_ratio, args.val_ratio, args.test_ratio,
            args.seed,
        )

    print(f"Split: train={len(train)}, val={len(val)}, test={len(test)}")

    # Check for leakage
    leaks = check_leakage(train, val, test)
    if leaks:
        print("\n❌ LEAKAGE DETECTED:")
        for leak in leaks:
            print(f"  - {leak}")
        return 1
    print("✅ No review_id leakage detected")

    # Write splits
    output_dir.mkdir(parents=True, exist_ok=True)

    train_norm = reviews_to_normalized_jsonl(train, output_dir / "train.jsonl")
    val_norm = reviews_to_normalized_jsonl(val, output_dir / "val.jsonl")
    test_norm = reviews_to_normalized_jsonl(test, output_dir / "test.jsonl")

    train_agg = reviews_to_aggregated_jsonl(train, output_dir / "train_aggregated.jsonl")
    val_agg = reviews_to_aggregated_jsonl(val, output_dir / "val_aggregated.jsonl")
    test_agg = reviews_to_aggregated_jsonl(test, output_dir / "test_aggregated.jsonl")

    # Compute stats
    train_stats = compute_split_stats(train, taxonomy)
    val_stats = compute_split_stats(val, taxonomy)
    test_stats = compute_split_stats(test, taxonomy)

    # Check for possible text duplicates across partitions
    train_texts = {r.text for r in train}
    val_texts = {r.text for r in val}
    test_texts = {r.text for r in test}
    text_overlap_tv = len(train_texts & val_texts)
    text_overlap_tt = len(train_texts & test_texts)

    # Save manifest
    manifest = {
        "split_timestamp": datetime.now().isoformat(),
        "strategy": strategy,
        "seed": args.seed,
        "ratios": {
            "train": args.train_ratio,
            "val": args.val_ratio,
            "test": args.test_ratio,
        },
        "partitions": {
            "train": {
                **train_stats,
                "file": str(train_norm),
                "file_hash": compute_file_hash(train_norm),
                "aggregated_file": str(train_agg),
                "aggregated_hash": compute_file_hash(train_agg),
            },
            "val": {
                **val_stats,
                "file": str(val_norm),
                "file_hash": compute_file_hash(val_norm),
                "aggregated_file": str(val_agg),
                "aggregated_hash": compute_file_hash(val_agg),
            },
            "test": {
                **test_stats,
                "file": str(test_norm),
                "file_hash": compute_file_hash(test_norm),
                "aggregated_file": str(test_agg),
                "aggregated_hash": compute_file_hash(test_agg),
            },
        },
        "leakage_check": "passed",
        "text_duplicates_across_partitions": {
            "train_val": text_overlap_tv,
            "train_test": text_overlap_tt,
        },
    }

    manifest_path = output_dir / "split_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\nManifest saved to {manifest_path}")
    if text_overlap_tv > 0 or text_overlap_tt > 0:
        print(f"⚠️ Possible text duplicates across partitions: "
              f"train-val={text_overlap_tv}, train-test={text_overlap_tt}")

    print("\n✅ Dataset split complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
