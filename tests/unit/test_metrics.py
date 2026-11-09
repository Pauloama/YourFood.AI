"""Unit tests for metrics calculation."""

import numpy as np
import pytest
from absa.metrics import (
    PipelinePrediction,
    compute_aspect_metrics,
    compute_pipeline_metrics,
    compute_sentiment_metrics,
    find_optimal_thresholds,
)
from absa.taxonomy import get_taxonomy


def test_aspect_metrics_calculation():
    tax = get_taxonomy()
    # 3 samples, 12 aspects
    y_true = np.zeros((3, 12), dtype=int)
    y_pred = np.zeros((3, 12), dtype=int)

    # Sample 0: true sabor (0), pred sabor (0) -> exact match
    y_true[0, 0] = 1
    y_pred[0, 0] = 1

    # Sample 1: true entrega (10), pred nothing -> fn
    y_true[1, 10] = 1

    # Sample 2: no aspects true, no aspects pred -> true negative
    metrics = compute_aspect_metrics(y_true, y_pred, aspect_names=tax.aspect_codes)

    assert "macro_f1" in metrics
    assert "micro_f1" in metrics
    assert "exact_match_ratio" in metrics
    assert metrics["exact_match_ratio"] == pytest.approx(2 / 3, abs=1e-3)  # samples 0 and 2 match completely
    assert "sabor" in metrics["per_aspect"]
    assert metrics["per_aspect"]["sabor"]["f1"] == 1.0


def test_optimal_thresholds_search():
    tax = get_taxonomy()
    # 4 samples, 12 aspects
    y_true = np.zeros((4, 12), dtype=int)
    y_prob = np.zeros((4, 12), dtype=float)

    # For aspect 0 (sabor)
    y_true[:, 0] = [1, 1, 0, 0]
    y_prob[:, 0] = [0.8, 0.6, 0.4, 0.2]

    # Threshold 0.5 separates perfectly
    res = find_optimal_thresholds(y_true, y_prob, aspect_names=tax.aspect_codes)
    assert "per_aspect_thresholds" in res
    assert 0.4 < res["per_aspect_thresholds"]["sabor"] <= 0.6
    assert res["per_aspect_f1_at_threshold"]["sabor"] == 1.0


def test_sentiment_metrics_calculation():
    y_true = ["positivo", "negativo", "neutro", "positivo"]
    y_pred = ["positivo", "negativo", "positivo", "positivo"]
    aspects = ["sabor", "temperatura", "embalagem", "sabor"]

    metrics = compute_sentiment_metrics(y_true, y_pred, aspects=aspects)
    assert metrics["accuracy"] == 0.75
    assert "macro_f1" in metrics
    assert "per_class" in metrics
    assert "positivo" in metrics["per_class"]
    assert "per_aspect" in metrics
    assert "sabor" in metrics["per_aspect"]


def test_pipeline_integrated_metrics():
    tax = get_taxonomy()
    preds = [
        # Review 1: perfectly correct
        PipelinePrediction(
            review_id="r1",
            predicted_pairs=[("sabor", "positivo"), ("temperatura", "negativo")],
            true_pairs=[("sabor", "positivo"), ("temperatura", "negativo")],
            latency_ms=45.0,
            num_aspects_predicted=2,
        ),
        # Review 2: aspect right, sentiment wrong
        PipelinePrediction(
            review_id="r2",
            predicted_pairs=[("sabor", "negativo")],
            true_pairs=[("sabor", "positivo")],
            latency_ms=30.0,
            num_aspects_predicted=1,
        ),
        # Review 3: false positive aspect
        PipelinePrediction(
            review_id="r3",
            predicted_pairs=[("tempo_entrega", "positivo")],
            true_pairs=[],
            latency_ms=25.0,
            num_aspects_predicted=1,
        ),
    ]

    metrics = compute_pipeline_metrics(preds, taxonomy=tax)
    assert metrics["total_reviews_evaluated"] == 3
    assert metrics["fully_correct_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert metrics["pair_metrics"]["precision"] > 0
    assert metrics["pair_metrics"]["recall"] > 0
    assert metrics["error_breakdown"]["total_sentiment_errors"] == 1
    assert "tempo_entrega" in metrics["error_breakdown"]["false_positives_by_aspect"]
    assert "p50_ms" in metrics["latency"]
