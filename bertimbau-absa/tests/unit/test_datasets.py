"""Unit tests for datasets and data validation."""

import pytest
from absa.datasets import (
    AspectAnnotation,
    ReviewRecord,
    detect_conflicts,
    records_to_reviews,
)
from absa.taxonomy import get_taxonomy


def test_review_to_multilabel_vector():
    tax = get_taxonomy()
    review = ReviewRecord(
        review_id="r1",
        text="A comida estava saborosa e bem servida.",
        annotations=[
            AspectAnnotation(aspect="sabor", sentiment="positivo"),
            AspectAnnotation(aspect="quantidade", sentiment="positivo"),
        ],
    )
    vector = review.to_multilabel_vector(tax)
    assert len(vector) == 12
    # sabor is index 0, quantidade is index 2
    assert vector[tax.aspect_to_index("sabor")] == 1
    assert vector[tax.aspect_to_index("quantidade")] == 1
    assert vector[tax.aspect_to_index("temperatura")] == 0
    assert sum(vector) == 2


def test_review_without_aspects_vector():
    tax = get_taxonomy()
    review = ReviewRecord(
        review_id="r2",
        text="Nota 1, não gostei.",
        annotations=[],
    )
    vector = review.to_multilabel_vector(tax)
    assert len(vector) == 12
    assert sum(vector) == 0


def test_detect_sentiment_conflicts():
    review_conflict = ReviewRecord(
        review_id="conf1",
        text="O sabor estava bom no início mas depois o sabor ficou horrível.",
        annotations=[
            AspectAnnotation(aspect="sabor", sentiment="positivo"),
            AspectAnnotation(aspect="sabor", sentiment="negativo"),
        ],
    )
    review_ok = ReviewRecord(
        review_id="ok1",
        text="Sabor ótimo e entrega rápida.",
        annotations=[
            AspectAnnotation(aspect="sabor", sentiment="positivo"),
            AspectAnnotation(aspect="tempo_entrega", sentiment="positivo"),
        ],
    )
    conflicts = detect_conflicts([review_conflict, review_ok])
    assert len(conflicts) == 1
    assert conflicts[0]["review_id"] == "conf1"
    assert conflicts[0]["aspect"] == "sabor"
    assert conflicts[0]["sentiments"] == ["negativo", "positivo"]


def test_records_to_reviews_grouping():
    records = [
        {"review_id": "10", "text": "Pizza boa e quente", "aspect": "sabor", "sentiment": "positivo"},
        {"review_id": "10", "text": "Pizza boa e quente", "aspect": "temperatura", "sentiment": "positivo"},
        {"review_id": "11", "text": "Ruim", "aspect": None, "sentiment": None},
    ]
    reviews = records_to_reviews(records)
    assert len(reviews) == 2
    r10 = next(r for r in reviews if r.review_id == "10")
    assert len(r10.annotations) == 2
    r11 = next(r for r in reviews if r.review_id == "11")
    assert len(r11.annotations) == 0
