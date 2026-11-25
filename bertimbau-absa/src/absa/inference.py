"""Inference engine for the ABSA pipeline.

Executes the two-stage inference:
1. AspectDetector: detects aspects using calibrated thresholds
2. SentimentClassifier: classifies sentiment for each detected aspect
3. Taxonomy: assigns business entity to each aspect
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch
from transformers import PreTrainedTokenizerBase

from .logging_config import get_logger
from .models.aspect_detector import AspectDetector, load_aspect_detector_artifact
from .models.sentiment_classifier import (
    SentimentClassifier,
    load_sentiment_classifier_artifact,
)
from .preprocessing import normalize_text
from .taxonomy import Taxonomy, get_taxonomy

logger = get_logger(__name__)


@dataclass
class AspectSentimentResult:
    """Result for a single detected aspect."""
    entity: str
    aspect: str
    aspect_probability: float
    sentiment: str
    sentiment_probability: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity": self.entity,
            "aspect": self.aspect,
            "aspectProbability": round(self.aspect_probability, 4),
            "sentiment": self.sentiment,
            "sentimentProbability": round(self.sentiment_probability, 4),
        }


@dataclass
class ReviewAnalysisResult:
    """Result for analyzing a full review."""
    review_id: str
    text: str
    aspects: list[AspectSentimentResult] = field(default_factory=list)
    model_versions: dict[str, str] = field(default_factory=dict)
    processing_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "reviewId": self.review_id,
            "text": self.text,
            "aspects": [a.to_dict() for a in self.aspects],
            "modelVersions": self.model_versions,
            "processingTimeMs": round(self.processing_time_ms, 2),
        }


class ABSAPipeline:
    """Integrated ABSA pipeline holding both models and thresholds."""

    def __init__(
        self,
        aspect_detector: AspectDetector,
        aspect_tokenizer: PreTrainedTokenizerBase,
        sentiment_classifier: SentimentClassifier,
        sentiment_tokenizer: PreTrainedTokenizerBase,
        thresholds: dict[str, float] | None = None,
        taxonomy: Taxonomy | None = None,
        aspect_version: str = "bertimbau-aspects-v1",
        sentiment_version: str = "bertimbau-aspect-sentiment-v1",
        device: torch.device | None = None,
        max_length: int = 128,
    ) -> None:
        self.aspect_detector = aspect_detector
        self.aspect_tokenizer = aspect_tokenizer
        self.sentiment_classifier = sentiment_classifier
        self.sentiment_tokenizer = sentiment_tokenizer
        self.taxonomy = taxonomy or get_taxonomy()
        self.aspect_version = aspect_version
        self.sentiment_version = sentiment_version
        self.max_length = max_length

        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = device

        self.aspect_detector.to(self.device).eval()
        self.sentiment_classifier.to(self.device).eval()

        # Set default 0.5 thresholds if none provided
        self.thresholds: dict[str, float] = {}
        for code in self.taxonomy.aspect_codes:
            if thresholds and code in thresholds:
                self.thresholds[code] = float(thresholds[code])
            else:
                self.thresholds[code] = 0.5

    @classmethod
    def from_artifacts(
        cls,
        aspect_detector_dir: Path | str,
        sentiment_classifier_dir: Path | str,
        taxonomy: Taxonomy | None = None,
        device: torch.device | None = None,
        aspect_version: str = "bertimbau-aspects-v1",
        sentiment_version: str = "bertimbau-aspect-sentiment-v1",
    ) -> ABSAPipeline:
        """Load pipeline from exported artifact directories."""
        if device is None:
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        detector, aspect_tok, thresholds = load_aspect_detector_artifact(
            artifact_dir=aspect_detector_dir,
            device=device,
        )

        classifier, sent_tok = load_sentiment_classifier_artifact(
            artifact_dir=sentiment_classifier_dir,
            device=device,
        )

        return cls(
            aspect_detector=detector,
            aspect_tokenizer=aspect_tok,
            sentiment_classifier=classifier,
            sentiment_tokenizer=sent_tok,
            thresholds=thresholds,
            taxonomy=taxonomy,
            aspect_version=aspect_version,
            sentiment_version=sentiment_version,
            device=device,
        )

    @torch.inference_mode()
    def analyze_review(
        self,
        review_id: str,
        text: str,
    ) -> ReviewAnalysisResult:
        """Analyze a single review through the two-stage pipeline.

        Args:
            review_id: Review identifier.
            text: Raw review text.

        Returns:
            ReviewAnalysisResult with detected aspects and sentiments.
        """
        start_time = time.perf_counter()
        normalized_text = normalize_text(text)

        # Stage 1: Detect aspects
        encoding = self.aspect_tokenizer(
            normalized_text,
            truncation=True,
            max_length=self.max_length,
            padding=True,
            return_tensors="pt",
        )
        input_ids = encoding["input_ids"].to(self.device)
        attention_mask = encoding["attention_mask"].to(self.device)
        token_type_ids = encoding.get("token_type_ids")
        if token_type_ids is not None:
            token_type_ids = token_type_ids.to(self.device)

        probs = self.aspect_detector.predict_proba(
            input_ids, attention_mask, token_type_ids
        ).squeeze(0).cpu().numpy()

        detected_aspects: list[tuple[str, float]] = []
        for i, aspect_code in enumerate(self.taxonomy.aspect_codes):
            prob = float(probs[i])
            thresh = self.thresholds.get(aspect_code, 0.5)
            if prob >= thresh:
                detected_aspects.append((aspect_code, prob))

        # Stage 2: Classify sentiment for detected aspects only
        results: list[AspectSentimentResult] = []
        for aspect_code, aspect_prob in detected_aspects:
            sent_encoding = self.sentiment_tokenizer(
                text=normalized_text,
                text_pair=aspect_code,
                truncation=True,
                max_length=self.max_length,
                padding=True,
                return_tensors="pt",
            )
            s_input_ids = sent_encoding["input_ids"].to(self.device)
            s_attention_mask = sent_encoding["attention_mask"].to(self.device)
            s_token_type_ids = sent_encoding.get("token_type_ids")
            if s_token_type_ids is not None:
                s_token_type_ids = s_token_type_ids.to(self.device)

            sent_probs = self.sentiment_classifier.predict_proba(
                s_input_ids, s_attention_mask, s_token_type_ids
            ).squeeze(0).cpu().numpy()

            best_idx = int(np.argmax(sent_probs))
            sentiment_name = self.taxonomy.index_to_sentiment(best_idx)
            sentiment_prob = float(sent_probs[best_idx])
            entity = self.taxonomy.get_entity(aspect_code)

            results.append(
                AspectSentimentResult(
                    entity=entity,
                    aspect=aspect_code,
                    aspect_probability=aspect_prob,
                    sentiment=sentiment_name,
                    sentiment_probability=sentiment_prob,
                )
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return ReviewAnalysisResult(
            review_id=review_id,
            text=text,
            aspects=results,
            model_versions={
                "aspectDetector": self.aspect_version,
                "sentimentClassifier": self.sentiment_version,
                "taxonomy": self.taxonomy.version,
            },
            processing_time_ms=elapsed_ms,
        )

    def analyze_batch(
        self,
        reviews: list[dict[str, str]],
    ) -> list[ReviewAnalysisResult]:
        """Analyze a batch of reviews."""
        return [
            self.analyze_review(
                review_id=str(r.get("reviewId", r.get("review_id", f"idx_{i}"))),
                text=str(r.get("text", "")),
            )
            for i, r in enumerate(reviews)
        ]

    @torch.inference_mode()
    def classify_sentiment_diagnostic(
        self,
        text: str,
        aspect: str,
    ) -> dict[str, Any]:
        """Diagnostic endpoint to test Model 2 independently."""
        if not self.taxonomy.is_valid_aspect(aspect):
            raise ValueError(
                f"Aspect '{aspect}' is not valid in taxonomy. "
                f"Valid aspects: {self.taxonomy.aspect_codes}"
            )

        normalized_text = normalize_text(text)
        sent_encoding = self.sentiment_tokenizer(
            text=normalized_text,
            text_pair=aspect,
            truncation=True,
            max_length=self.max_length,
            padding=True,
            return_tensors="pt",
        )
        input_ids = sent_encoding["input_ids"].to(self.device)
        attention_mask = sent_encoding["attention_mask"].to(self.device)
        token_type_ids = sent_encoding.get("token_type_ids")
        if token_type_ids is not None:
            token_type_ids = token_type_ids.to(self.device)

        probs = self.sentiment_classifier.predict_proba(
            input_ids, attention_mask, token_type_ids
        ).squeeze(0).cpu().numpy()

        best_idx = int(np.argmax(probs))
        sentiment_name = self.taxonomy.index_to_sentiment(best_idx)

        all_probs = {
            self.taxonomy.index_to_sentiment(i): round(float(probs[i]), 4)
            for i in range(len(probs))
        }

        return {
            "text": text,
            "aspect": aspect,
            "entity": self.taxonomy.get_entity(aspect),
            "predictedSentiment": sentiment_name,
            "probability": round(float(probs[best_idx]), 4),
            "probabilities": all_probs,
        }
