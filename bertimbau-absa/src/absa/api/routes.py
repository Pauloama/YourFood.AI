"""API routes for ABSA service."""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from ..config import APIConfig
from ..inference import ABSAPipeline
from ..logging_config import get_logger
from ..taxonomy import get_taxonomy
from .dependencies import (
    get_api_config,
    get_pipeline,
    is_aspect_model_loaded,
    is_sentiment_model_loaded,
)
from .schemas import (
    BatchAnalysisRequest,
    BatchAnalysisResponse,
    DiagnosticSentimentRequest,
    DiagnosticSentimentResponse,
    HealthResponse,
    ReviewAnalysisRequest,
    ReviewAnalysisResponse,
)

logger = get_logger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Monitoring"])
def health_check() -> HealthResponse:
    """Return health status and loaded model availability."""
    return HealthResponse(
        status="ok",
        aspectModelLoaded=is_aspect_model_loaded(),
        sentimentModelLoaded=is_sentiment_model_loaded(),
    )


@router.post(
    "/api/v1/reviews/analyze",
    response_model=ReviewAnalysisResponse,
    tags=["Analysis"],
)
def analyze_review(
    request: ReviewAnalysisRequest,
    pipeline: Annotated[ABSAPipeline, Depends(get_pipeline)],
    config: Annotated[APIConfig, Depends(get_api_config)],
    x_correlation_id: Annotated[str | None, Header()] = None,
) -> ReviewAnalysisResponse:
    """Analyze a single review for aspects and sentiments."""
    if len(request.text) > config.max_text_length:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Text length exceeds maximum allowed length of {config.max_text_length} characters.",
        )

    res = pipeline.analyze_review(review_id=request.reviewId, text=request.text)

    logger.info(
        "review_analyzed",
        review_id=request.reviewId,
        aspect_count=len(res.aspects),
        latency_ms=res.processing_time_ms,
        correlation_id=x_correlation_id,
    )

    return ReviewAnalysisResponse(**res.to_dict())


@router.post(
    "/api/v1/reviews/analyze-batch",
    response_model=BatchAnalysisResponse,
    tags=["Analysis"],
)
def analyze_batch(
    request: BatchAnalysisRequest,
    pipeline: Annotated[ABSAPipeline, Depends(get_pipeline)],
    config: Annotated[APIConfig, Depends(get_api_config)],
    x_correlation_id: Annotated[str | None, Header()] = None,
) -> BatchAnalysisResponse:
    """Analyze a batch of reviews."""
    if len(request.reviews) > config.max_batch_size:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Batch size {len(request.reviews)} exceeds maximum allowed of {config.max_batch_size}.",
        )

    start_total = time.perf_counter()
    responses: list[ReviewAnalysisResponse] = []

    for r in request.reviews:
        if len(r.text) > config.max_text_length:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Text in review {r.reviewId} exceeds max text length {config.max_text_length}.",
            )
        res = pipeline.analyze_review(review_id=r.reviewId, text=r.text)
        responses.append(ReviewAnalysisResponse(**res.to_dict()))

    total_ms = (time.perf_counter() - start_total) * 1000.0

    logger.info(
        "batch_analyzed",
        batch_size=len(request.reviews),
        total_latency_ms=round(total_ms, 2),
        correlation_id=x_correlation_id,
    )

    return BatchAnalysisResponse(
        results=responses,
        totalReviews=len(responses),
        totalProcessingTimeMs=round(total_ms, 2),
    )


@router.post(
    "/api/v1/reviews/classify-sentiment",
    response_model=DiagnosticSentimentResponse,
    tags=["Diagnostic"],
)
def classify_sentiment_diagnostic(
    request: DiagnosticSentimentRequest,
    pipeline: Annotated[ABSAPipeline, Depends(get_pipeline)],
    taxonomy=Depends(get_taxonomy),
    x_correlation_id: Annotated[str | None, Header()] = None,
) -> DiagnosticSentimentResponse:
    """Classify sentiment conditioned on a specific aspect (diagnostic endpoint)."""
    if not taxonomy.is_valid_aspect(request.aspect):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Aspect '{request.aspect}' is outside taxonomy. Valid aspects: {taxonomy.aspect_codes}",
        )

    result = pipeline.classify_sentiment_diagnostic(
        text=request.text,
        aspect=request.aspect,
    )

    logger.info(
        "sentiment_classified_diagnostic",
        aspect=request.aspect,
        predicted=result["predictedSentiment"],
        correlation_id=x_correlation_id,
    )

    return DiagnosticSentimentResponse(**result)
