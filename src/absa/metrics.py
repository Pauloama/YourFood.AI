"""Metrics computation for the ABSA pipeline.

Provides metrics for:
- Multi-label aspect detection (Model 1)
- Aspect-conditioned sentiment classification (Model 2)
- Integrated pipeline evaluation
"""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    hamming_loss,
    precision_recall_curve,
    precision_score,
    recall_score,
)

from .taxonomy import Taxonomy, get_taxonomy


# =============================================================================
# Aspect Detector Metrics (Model 1 - Multi-label)
# =============================================================================


def compute_aspect_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: np.ndarray | None = None,
    aspect_names: list[str] | None = None,
) -> dict[str, Any]:
    """Compute all metrics for the multi-label aspect detector.

    Args:
        y_true: Ground truth binary matrix (n_samples, n_aspects).
        y_pred: Predicted binary matrix (n_samples, n_aspects).
        y_prob: Predicted probability matrix (n_samples, n_aspects). Optional.
        aspect_names: List of aspect names in order.

    Returns:
        Dictionary with all computed metrics.
    """
    if aspect_names is None:
        taxonomy = get_taxonomy()
        aspect_names = taxonomy.aspect_codes

    n_aspects = y_true.shape[1]
    assert n_aspects == len(aspect_names), (
        f"Mismatch: {n_aspects} aspects in data vs {len(aspect_names)} names"
    )

    # Per-aspect metrics
    per_aspect: dict[str, dict[str, float]] = {}
    for i, name in enumerate(aspect_names):
        true_col = y_true[:, i]
        pred_col = y_pred[:, i]
        support = int(true_col.sum())
        if support > 0:
            f1 = float(f1_score(true_col, pred_col, zero_division=0))
            prec = float(precision_score(true_col, pred_col, zero_division=0))
            rec = float(recall_score(true_col, pred_col, zero_division=0))
        else:
            f1 = 0.0
            prec = 0.0
            rec = 0.0
        per_aspect[name] = {
            "f1": round(f1, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "support": support,
            "predicted_positive": int(pred_col.sum()),
        }

    # Macro and micro F1
    macro_f1 = float(np.mean([m["f1"] for m in per_aspect.values()]))
    micro_f1 = float(f1_score(y_true.ravel(), y_pred.ravel(), zero_division=0))
    macro_precision = float(np.mean([m["precision"] for m in per_aspect.values()]))
    macro_recall = float(np.mean([m["recall"] for m in per_aspect.values()]))

    # Exact match ratio
    exact_match = float(np.mean(np.all(y_true == y_pred, axis=1)))

    # Hamming loss
    h_loss = float(hamming_loss(y_true, y_pred))

    # Co-occurrence matrix
    cooccurrence = np.zeros((n_aspects, n_aspects), dtype=int)
    for row in y_pred:
        active = np.where(row == 1)[0]
        for i in active:
            for j in active:
                cooccurrence[i][j] += 1

    result: dict[str, Any] = {
        "macro_f1": round(macro_f1, 4),
        "micro_f1": round(micro_f1, 4),
        "macro_precision": round(macro_precision, 4),
        "macro_recall": round(macro_recall, 4),
        "exact_match_ratio": round(exact_match, 4),
        "hamming_loss": round(h_loss, 4),
        "per_aspect": per_aspect,
        "cooccurrence_matrix": {
            "labels": aspect_names,
            "matrix": cooccurrence.tolist(),
        },
    }

    # Precision-recall curves per aspect (if probabilities available)
    if y_prob is not None:
        pr_curves: dict[str, dict] = {}
        for i, name in enumerate(aspect_names):
            true_col = y_true[:, i]
            prob_col = y_prob[:, i]
            if true_col.sum() > 0:
                precisions, recalls, thresholds = precision_recall_curve(
                    true_col, prob_col
                )
                step = max(1, len(precisions) // 50)
                pr_curves[name] = {
                    "precisions": [round(float(p), 4) for p in precisions[::step]],
                    "recalls": [round(float(r), 4) for r in recalls[::step]],
                    "num_points": len(precisions),
                }
        result["precision_recall_curves"] = pr_curves

    return result


def find_optimal_thresholds(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    aspect_names: list[str] | None = None,
    search_min: float = 0.10,
    search_max: float = 0.90,
    search_steps: int = 81,
) -> dict[str, Any]:
    """Find optimal per-aspect thresholds that maximize F1.

    Args:
        y_true: Ground truth binary matrix (n_samples, n_aspects).
        y_prob: Predicted probability matrix (n_samples, n_aspects).
        aspect_names: List of aspect names in order.
        search_min: Minimum threshold to search.
        search_max: Maximum threshold to search.
        search_steps: Number of threshold steps to evaluate.

    Returns:
        Dictionary with optimal thresholds and comparison to global.
    """
    if aspect_names is None:
        taxonomy = get_taxonomy()
        aspect_names = taxonomy.aspect_codes

    n_aspects = y_true.shape[1]
    thresholds_to_try = np.linspace(search_min, search_max, search_steps)

    per_aspect_thresholds: dict[str, float] = {}
    per_aspect_f1_at_threshold: dict[str, float] = {}

    for i, name in enumerate(aspect_names):
        true_col = y_true[:, i]
        prob_col = y_prob[:, i]

        best_f1 = -1.0
        best_thresh = 0.5

        for thresh in thresholds_to_try:
            pred_col = (prob_col >= thresh).astype(int)
            f1 = float(f1_score(true_col, pred_col, zero_division=0))
            if f1 > best_f1:
                best_f1 = f1
                best_thresh = float(thresh)

        per_aspect_thresholds[name] = round(best_thresh, 4)
        per_aspect_f1_at_threshold[name] = round(best_f1, 4)

    # Compare with global 0.5 threshold
    global_pred = (y_prob >= 0.5).astype(int)
    global_metrics = compute_aspect_metrics(y_true, global_pred, y_prob, aspect_names)

    optimal_pred = np.zeros_like(y_prob, dtype=int)
    for i, name in enumerate(aspect_names):
        optimal_pred[:, i] = (y_prob[:, i] >= per_aspect_thresholds[name]).astype(int)
    optimal_metrics = compute_aspect_metrics(y_true, optimal_pred, y_prob, aspect_names)

    return {
        "per_aspect_thresholds": per_aspect_thresholds,
        "per_aspect_f1_at_threshold": per_aspect_f1_at_threshold,
        "comparison": {
            "global_0.5_macro_f1": global_metrics["macro_f1"],
            "optimized_macro_f1": optimal_metrics["macro_f1"],
            "improvement": round(
                optimal_metrics["macro_f1"] - global_metrics["macro_f1"], 4
            ),
        },
    }


# =============================================================================
# Sentiment Classifier Metrics (Model 2)
# =============================================================================


def compute_sentiment_metrics(
    y_true: list[str] | np.ndarray,
    y_pred: list[str] | np.ndarray,
    aspects: list[str] | None = None,
    sentiment_names: list[str] | None = None,
) -> dict[str, Any]:
    """Compute all metrics for the sentiment classifier.

    Args:
        y_true: Ground truth sentiment labels.
        y_pred: Predicted sentiment labels.
        aspects: Corresponding aspect for each sample (for per-aspect breakdown).
        sentiment_names: List of sentiment class names.

    Returns:
        Dictionary with all computed metrics.
    """
    if sentiment_names is None:
        taxonomy = get_taxonomy()
        sentiment_names = list(taxonomy.sentiments)

    y_true_list = list(y_true)
    y_pred_list = list(y_pred)

    # Overall metrics
    macro_f1 = float(f1_score(y_true_list, y_pred_list, average="macro", zero_division=0))
    micro_f1 = float(f1_score(y_true_list, y_pred_list, average="micro", zero_division=0))
    accuracy = float(np.mean(np.array(y_true_list) == np.array(y_pred_list)))

    # Per-class metrics
    report = classification_report(
        y_true_list, y_pred_list,
        labels=sentiment_names,
        output_dict=True,
        zero_division=0,
    )

    per_class: dict[str, dict[str, float]] = {}
    for cls in sentiment_names:
        if cls in report:
            per_class[cls] = {
                "precision": round(report[cls]["precision"], 4),
                "recall": round(report[cls]["recall"], 4),
                "f1": round(report[cls]["f1-score"], 4),
                "support": int(report[cls]["support"]),
            }

    # Confusion matrix
    cm = confusion_matrix(y_true_list, y_pred_list, labels=sentiment_names)

    result: dict[str, Any] = {
        "macro_f1": round(macro_f1, 4),
        "micro_f1": round(micro_f1, 4),
        "accuracy": round(accuracy, 4),
        "per_class": per_class,
        "confusion_matrix": {
            "labels": sentiment_names,
            "matrix": cm.tolist(),
        },
    }

    # Per-aspect breakdown
    if aspects is not None:
        per_aspect_metrics: dict[str, dict[str, Any]] = {}
        aspect_groups: dict[str, dict[str, list]] = defaultdict(
            lambda: {"true": [], "pred": []}
        )

        for asp, true_s, pred_s in zip(aspects, y_true_list, y_pred_list):
            aspect_groups[asp]["true"].append(true_s)
            aspect_groups[asp]["pred"].append(pred_s)

        for asp, group in sorted(aspect_groups.items()):
            asp_true = group["true"]
            asp_pred = group["pred"]
            asp_f1 = float(f1_score(asp_true, asp_pred, average="macro", zero_division=0))
            asp_acc = float(np.mean(np.array(asp_true) == np.array(asp_pred)))

            per_aspect_entry: dict[str, Any] = {
                "macro_f1": round(asp_f1, 4),
                "accuracy": round(asp_acc, 4),
                "support": len(asp_true),
            }

            # Per-aspect confusion matrix if enough data
            if len(asp_true) >= 10:
                asp_cm = confusion_matrix(asp_true, asp_pred, labels=sentiment_names)
                per_aspect_entry["confusion_matrix"] = {
                    "labels": sentiment_names,
                    "matrix": asp_cm.tolist(),
                }

            per_aspect_metrics[asp] = per_aspect_entry

        result["per_aspect"] = per_aspect_metrics

    return result


# =============================================================================
# Integrated Pipeline Metrics
# =============================================================================


@dataclass
class PipelinePrediction:
    """A single pipeline prediction for one review."""
    review_id: str
    predicted_pairs: list[tuple[str, str]]  # (aspect, sentiment)
    true_pairs: list[tuple[str, str]]       # (aspect, sentiment)
    latency_ms: float = 0.0
    num_aspects_predicted: int = 0


def compute_pipeline_metrics(
    predictions: list[PipelinePrediction],
    taxonomy: Taxonomy | None = None,
) -> dict[str, Any]:
    """Compute integrated pipeline metrics.

    Evaluates the full flow: aspect detection -> sentiment classification.

    Args:
        predictions: List of pipeline predictions.
        taxonomy: Taxonomy instance.

    Returns:
        Dictionary with comprehensive pipeline metrics.
    """
    if taxonomy is None:
        taxonomy = get_taxonomy()

    # Pair-level metrics
    total_true_pairs = 0
    total_pred_pairs = 0
    total_correct_pairs = 0
    total_correct_aspect_wrong_sentiment = 0
    fully_correct_reviews = 0
    total_reviews = len(predictions)

    # Per-aspect error tracking
    false_positives_by_aspect: Counter = Counter()
    false_negatives_by_aspect: Counter = Counter()
    sentiment_errors_by_aspect: Counter = Counter()

    # Latency tracking
    latencies: list[float] = []
    aspects_per_review: list[int] = []

    for pred in predictions:
        true_set = set(pred.true_pairs)
        pred_set = set(pred.predicted_pairs)

        total_true_pairs += len(true_set)
        total_pred_pairs += len(pred_set)

        # Correct pairs (exact match of aspect + sentiment)
        correct = true_set & pred_set
        total_correct_pairs += len(correct)

        # Check if review is fully correct
        if true_set == pred_set:
            fully_correct_reviews += 1

        # Analyze errors
        true_aspects = {a for a, s in true_set}
        pred_aspects = {a for a, s in pred_set}

        # False positives (predicted but not true)
        for a in pred_aspects - true_aspects:
            false_positives_by_aspect[a] += 1

        # False negatives (true but not predicted)
        for a in true_aspects - pred_aspects:
            false_negatives_by_aspect[a] += 1

        # Sentiment errors (aspect correct but sentiment wrong)
        for a in true_aspects & pred_aspects:
            true_sents = {s for asp, s in true_set if asp == a}
            pred_sents = {s for asp, s in pred_set if asp == a}
            if true_sents != pred_sents:
                total_correct_aspect_wrong_sentiment += 1
                sentiment_errors_by_aspect[a] += 1

        latencies.append(pred.latency_ms)
        aspects_per_review.append(pred.num_aspects_predicted)

    # Compute pair-level precision/recall/F1
    pair_precision = (
        total_correct_pairs / total_pred_pairs
        if total_pred_pairs > 0 else 0.0
    )
    pair_recall = (
        total_correct_pairs / total_true_pairs
        if total_true_pairs > 0 else 0.0
    )
    pair_f1 = (
        2 * pair_precision * pair_recall / (pair_precision + pair_recall)
        if (pair_precision + pair_recall) > 0 else 0.0
    )

    fully_correct_rate = (
        fully_correct_reviews / total_reviews
        if total_reviews > 0 else 0.0
    )

    # Latency stats
    latency_array = np.array(latencies) if latencies else np.array([0.0])
    latency_stats = {
        "mean_ms": round(float(np.mean(latency_array)), 2),
        "p50_ms": round(float(np.percentile(latency_array, 50)), 2),
        "p95_ms": round(float(np.percentile(latency_array, 95)), 2),
        "p99_ms": round(float(np.percentile(latency_array, 99)), 2),
    }

    aspects_array = np.array(aspects_per_review) if aspects_per_review else np.array([0])
    avg_aspects = round(float(np.mean(aspects_array)), 2)

    return {
        "pair_metrics": {
            "precision": round(pair_precision, 4),
            "recall": round(pair_recall, 4),
            "f1": round(pair_f1, 4),
        },
        "fully_correct_rate": round(fully_correct_rate, 4),
        "error_breakdown": {
            "total_aspect_detection_errors": (
                sum(false_positives_by_aspect.values())
                + sum(false_negatives_by_aspect.values())
            ),
            "total_sentiment_errors": total_correct_aspect_wrong_sentiment,
            "false_positives_by_aspect": dict(false_positives_by_aspect.most_common()),
            "false_negatives_by_aspect": dict(false_negatives_by_aspect.most_common()),
            "sentiment_errors_by_aspect": dict(sentiment_errors_by_aspect.most_common()),
        },
        "latency": latency_stats,
        "avg_aspects_per_review": avg_aspects,
        "total_reviews_evaluated": total_reviews,
    }


def save_metrics_report(
    metrics: dict[str, Any],
    output_dir: Path | str,
    filename_prefix: str = "metrics",
) -> tuple[Path, Path]:
    """Save metrics as JSON and Markdown.

    Args:
        metrics: Metrics dictionary.
        output_dir: Output directory.
        filename_prefix: Prefix for output files.

    Returns:
        Tuple of (json_path, markdown_path).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = output_dir / f"{filename_prefix}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    # Markdown
    md_path = output_dir / f"{filename_prefix}.md"
    md_lines: list[str] = [f"# Metrics Report: {filename_prefix}", ""]

    def _render_dict(d: dict, level: int = 2) -> None:
        for key, value in d.items():
            if isinstance(value, dict):
                md_lines.append(f"{'#' * level} {key}")
                md_lines.append("")
                if all(isinstance(v, (int, float, str, bool)) for v in value.values()):
                    md_lines.append("| Metric | Value |")
                    md_lines.append("|---|---|")
                    for k, v in value.items():
                        md_lines.append(f"| {k} | {v} |")
                    md_lines.append("")
                else:
                    _render_dict(value, min(level + 1, 6))
            elif isinstance(value, list):
                md_lines.append(f"**{key}:** {len(value)} items")
                md_lines.append("")
            else:
                md_lines.append(f"**{key}:** `{value}`")
                md_lines.append("")

    _render_dict(metrics)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return json_path, md_path
