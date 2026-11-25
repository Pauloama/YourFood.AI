"""Integration tests for FastAPI endpoints."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from absa.api.dependencies import set_pipeline
from absa.api.main import app
from absa.inference import (
    ABSAPipeline,
    AspectSentimentResult,
    ReviewAnalysisResult,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check_without_models(client):
    set_pipeline(None)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["aspectModelLoaded"] is False
    assert data["sentimentModelLoaded"] is False


def test_analyze_when_models_not_loaded(client):
    set_pipeline(None)
    response = client.post(
        "/api/v1/reviews/analyze",
        json={"reviewId": "r1", "text": "Pizza boa"},
    )
    assert response.status_code == 503
    assert "models are not currently loaded" in response.json()["detail"]


@pytest.fixture
def mock_pipeline():
    mock = MagicMock(spec=ABSAPipeline)
    mock.aspect_detector = MagicMock()
    mock.sentiment_classifier = MagicMock()

    def _mock_analyze(review_id: str, text: str):
        if "sabor" in text or "gostoso" in text or "bom" in text:
            aspects = [
                AspectSentimentResult(
                    entity="produto",
                    aspect="sabor",
                    aspect_probability=0.95,
                    sentiment="positivo",
                    sentiment_probability=0.92,
                )
            ]
        else:
            aspects = []
        return ReviewAnalysisResult(
            review_id=review_id,
            text=text,
            aspects=aspects,
            model_versions={
                "aspectDetector": "bertimbau-aspects-v1",
                "sentimentClassifier": "bertimbau-aspect-sentiment-v1",
                "taxonomy": "food-reviews-taxonomy-v1",
            },
            processing_time_ms=12.5,
        )

    mock.analyze_review.side_effect = _mock_analyze

    def _mock_diagnostic(text: str, aspect: str):
        return {
            "text": text,
            "aspect": aspect,
            "entity": "produto",
            "predictedSentiment": "positivo",
            "probability": 0.94,
            "probabilities": {"positivo": 0.94, "negativo": 0.04, "neutro": 0.02},
        }

    mock.classify_sentiment_diagnostic.side_effect = _mock_diagnostic
    return mock


def test_analyze_review_success(client, mock_pipeline):
    set_pipeline(mock_pipeline)
    response = client.post(
        "/api/v1/reviews/analyze",
        json={"reviewId": "101", "text": "O hambúrguer estava muito bom!"},
        headers={"X-Correlation-ID": "test-corr-123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["reviewId"] == "101"
    assert len(data["aspects"]) == 1
    assert data["aspects"][0]["aspect"] == "sabor"
    assert data["aspects"][0]["entity"] == "produto"
    assert data["aspects"][0]["sentiment"] == "positivo"
    assert response.headers.get("X-Correlation-ID") == "test-corr-123"


def test_analyze_review_no_aspects(client, mock_pipeline):
    set_pipeline(mock_pipeline)
    response = client.post(
        "/api/v1/reviews/analyze",
        json={"reviewId": "102", "text": "Nota 1, não gostei."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["reviewId"] == "102"
    assert data["aspects"] == []


def test_analyze_empty_text_error(client, mock_pipeline):
    set_pipeline(mock_pipeline)
    response = client.post(
        "/api/v1/reviews/analyze",
        json={"reviewId": "103", "text": "    "},
    )
    assert response.status_code == 422


def test_analyze_batch_endpoint(client, mock_pipeline):
    set_pipeline(mock_pipeline)
    batch = {
        "reviews": [
            {"reviewId": "r1", "text": "Hambúrguer muito bom!"},
            {"reviewId": "r2", "text": "Não gostei."},
        ]
    }
    response = client.post("/api/v1/reviews/analyze-batch", json=batch)
    assert response.status_code == 200
    data = response.json()
    assert data["totalReviews"] == 2
    assert len(data["results"]) == 2


def test_diagnostic_sentiment_invalid_aspect(client, mock_pipeline):
    set_pipeline(mock_pipeline)
    response = client.post(
        "/api/v1/reviews/classify-sentiment",
        json={"text": "Comida boa", "aspect": "aspecto_invalido"},
    )
    assert response.status_code == 422
    assert "outside taxonomy" in response.json()["detail"]


def test_diagnostic_sentiment_valid(client, mock_pipeline):
    set_pipeline(mock_pipeline)
    response = client.post(
        "/api/v1/reviews/classify-sentiment",
        json={"text": "Comida boa", "aspect": "sabor"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["predictedSentiment"] == "positivo"
    assert data["aspect"] == "sabor"
