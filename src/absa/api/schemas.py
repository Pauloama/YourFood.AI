"""Pydantic schemas for the ABSA REST API."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    aspectModelLoaded: bool
    sentimentModelLoaded: bool


class ReviewAnalysisRequest(BaseModel):
    """Request to analyze a single review."""
    reviewId: str = Field(..., description="Unique review identifier", min_length=1)
    text: str = Field(..., description="Review text to analyze", min_length=1)

    @field_validator("text")
    @classmethod
    def validate_non_empty_text(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Review text must not be empty or whitespace only")
        return stripped


class BatchAnalysisRequest(BaseModel):
    """Request to analyze a batch of reviews."""
    reviews: list[ReviewAnalysisRequest] = Field(..., min_length=1)


class AspectSentimentItem(BaseModel):
    """Detected aspect with sentiment."""
    entity: str
    aspect: str
    aspectProbability: float = Field(..., ge=0.0, le=1.0)
    sentiment: str
    sentimentProbability: float = Field(..., ge=0.0, le=1.0)


class ReviewAnalysisResponse(BaseModel):
    """Full analysis response for a review."""
    reviewId: str
    text: str
    aspects: list[AspectSentimentItem]
    modelVersions: dict[str, str]
    processingTimeMs: float


class BatchAnalysisResponse(BaseModel):
    """Batch analysis response."""
    results: list[ReviewAnalysisResponse]
    totalReviews: int
    totalProcessingTimeMs: float


class DiagnosticSentimentRequest(BaseModel):
    """Request to classify sentiment for a specific aspect."""
    text: str = Field(..., min_length=1)
    aspect: str = Field(..., min_length=1)

    @field_validator("text")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Text must not be empty or whitespace only")
        return stripped


class DiagnosticSentimentResponse(BaseModel):
    """Diagnostic response for sentiment classification."""
    text: str
    aspect: str
    entity: str
    predictedSentiment: str
    probability: float
    probabilities: dict[str, float]
