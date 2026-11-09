"""Unit tests for API schemas."""

import pytest
from pydantic import ValidationError
from absa.api.schemas import (
    DiagnosticSentimentRequest,
    ReviewAnalysisRequest,
    ReviewAnalysisResponse,
)


def test_review_analysis_request_valid():
    req = ReviewAnalysisRequest(
        reviewId="101",
        text="A comida estava maravilhosa!",
    )
    assert req.reviewId == "101"
    assert req.text == "A comida estava maravilhosa!"


def test_review_analysis_request_empty_text_rejected():
    with pytest.raises(ValidationError):
        ReviewAnalysisRequest(reviewId="102", text="   ")


def test_review_analysis_request_empty_id_rejected():
    with pytest.raises(ValidationError):
        ReviewAnalysisRequest(reviewId="", text="Texto valido")


def test_diagnostic_request_empty_text():
    with pytest.raises(ValidationError):
        DiagnosticSentimentRequest(text="", aspect="sabor")


def test_review_response_serialization():
    data = {
        "reviewId": "101",
        "text": "Pizza boa",
        "aspects": [
            {
                "entity": "produto",
                "aspect": "sabor",
                "aspectProbability": 0.95,
                "sentiment": "positivo",
                "sentimentProbability": 0.98,
            }
        ],
        "modelVersions": {
            "aspectDetector": "bertimbau-aspects-v1",
            "sentimentClassifier": "bertimbau-aspect-sentiment-v1",
            "taxonomy": "food-reviews-taxonomy-v1",
        },
        "processingTimeMs": 52.3,
    }
    resp = ReviewAnalysisResponse(**data)
    d = resp.model_dump()
    assert d["reviewId"] == "101"
    assert len(d["aspects"]) == 1
    assert d["aspects"][0]["entity"] == "produto"
