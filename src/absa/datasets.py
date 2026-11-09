"""Dataset handling for the ABSA pipeline.

Supports loading from JSONL and CSV formats.
Handles conversion between normalized (one row per aspect occurrence)
and aggregated (one row per review) formats.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .preprocessing import normalize_text
from .taxonomy import Taxonomy, get_taxonomy


@dataclass
class AspectAnnotation:
    """A single aspect annotation for a review."""
    aspect: str
    sentiment: str
    evidence_text: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None


@dataclass
class ReviewRecord:
    """A single review with all its aspect annotations."""
    review_id: str
    text: str
    annotations: list[AspectAnnotation] = field(default_factory=list)
    rating: float | None = None
    user_id: str | None = None
    store_id: str | None = None
    order_id: str | None = None
    created_at: str | None = None
    requires_review: bool = False

    @property
    def has_aspects(self) -> bool:
        """Whether this review has any aspect annotations."""
        return len(self.annotations) > 0

    def to_multilabel_vector(self, taxonomy: Taxonomy | None = None) -> list[int]:
        """Convert annotations to a multi-label binary vector.

        Args:
            taxonomy: Taxonomy instance. Uses default if None.

        Returns:
            List of 0/1 values in canonical aspect order.
        """
        if taxonomy is None:
            taxonomy = get_taxonomy()
        vector = [0] * taxonomy.num_aspects
        for ann in self.annotations:
            if taxonomy.is_valid_aspect(ann.aspect):
                idx = taxonomy.aspect_to_index(ann.aspect)
                vector[idx] = 1
        return vector

    def to_normalized_rows(self) -> list[dict[str, Any]]:
        """Convert to normalized format (one row per aspect occurrence)."""
        if not self.annotations:
            return [{
                "review_id": self.review_id,
                "text": self.text,
                "aspect": None,
                "sentiment": None,
                "rating": self.rating,
                "user_id": self.user_id,
                "store_id": self.store_id,
                "order_id": self.order_id,
                "created_at": self.created_at,
                "requires_review": self.requires_review,
            }]
        rows = []
        for ann in self.annotations:
            rows.append({
                "review_id": self.review_id,
                "text": self.text,
                "aspect": ann.aspect,
                "sentiment": ann.sentiment,
                "rating": self.rating,
                "user_id": self.user_id,
                "store_id": self.store_id,
                "order_id": self.order_id,
                "created_at": self.created_at,
                "evidence_text": ann.evidence_text,
                "start_offset": ann.start_offset,
                "end_offset": ann.end_offset,
                "requires_review": self.requires_review,
            })
        return rows

    def to_aggregated_row(self) -> dict[str, Any]:
        """Convert to aggregated format (one row per review)."""
        aspects = [ann.aspect for ann in self.annotations]
        sentiments = {ann.aspect: ann.sentiment for ann in self.annotations}
        return {
            "review_id": self.review_id,
            "text": self.text,
            "aspects": aspects,
            "sentiments": sentiments,
            "rating": self.rating,
            "user_id": self.user_id,
            "store_id": self.store_id,
            "order_id": self.order_id,
            "created_at": self.created_at,
            "requires_review": self.requires_review,
        }


@dataclass
class ValidationError:
    """A single validation error."""
    review_id: str | None
    field: str
    error_type: str
    message: str
    severity: str = "error"  # "error" or "warning"


def load_jsonl(path: Path | str) -> list[dict[str, Any]]:
    """Load data from a JSONL file.

    Args:
        path: Path to the JSONL file.

    Returns:
        List of dictionaries, one per line.
    """
    path = Path(path)
    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON at line {line_num} in {path}: {e}"
                ) from e
    return records


def load_csv(path: Path | str) -> list[dict[str, Any]]:
    """Load data from a CSV file.

    Args:
        path: Path to the CSV file.

    Returns:
        List of dictionaries, one per row.
    """
    path = Path(path)
    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert empty strings to None
            cleaned = {k: (v if v != "" else None) for k, v in row.items()}
            records.append(cleaned)
    return records


def load_data(path: Path | str) -> list[dict[str, Any]]:
    """Load data from JSONL or CSV based on file extension.

    Args:
        path: Path to data file (.jsonl or .csv).

    Returns:
        List of record dictionaries.

    Raises:
        ValueError: If file extension is not supported.
    """
    path = Path(path)
    if path.suffix == ".jsonl":
        return load_jsonl(path)
    elif path.suffix == ".csv":
        return load_csv(path)
    else:
        raise ValueError(
            f"Unsupported file format: {path.suffix}. Use .jsonl or .csv"
        )


def records_to_reviews(
    records: list[dict[str, Any]],
) -> list[ReviewRecord]:
    """Convert normalized records to ReviewRecord objects.

    Groups records by review_id, collecting all aspect annotations.

    Args:
        records: List of normalized record dicts.

    Returns:
        List of ReviewRecord objects.
    """
    reviews_map: dict[str, ReviewRecord] = {}

    for rec in records:
        rid = str(rec.get("review_id", ""))
        text = str(rec.get("text", ""))

        if rid not in reviews_map:
            reviews_map[rid] = ReviewRecord(
                review_id=rid,
                text=normalize_text(text),
                rating=rec.get("rating"),
                user_id=rec.get("user_id"),
                store_id=rec.get("store_id"),
                order_id=rec.get("order_id"),
                created_at=rec.get("created_at"),
                requires_review=bool(rec.get("requires_review", False)),
            )

        aspect = rec.get("aspect")
        sentiment = rec.get("sentiment")

        if aspect is not None and sentiment is not None:
            reviews_map[rid].annotations.append(
                AspectAnnotation(
                    aspect=str(aspect),
                    sentiment=str(sentiment),
                    evidence_text=rec.get("evidence_text"),
                    start_offset=rec.get("start_offset"),
                    end_offset=rec.get("end_offset"),
                )
            )

        # Propagate requires_review
        if rec.get("requires_review"):
            reviews_map[rid].requires_review = True

    return list(reviews_map.values())


def reviews_to_normalized_jsonl(
    reviews: list[ReviewRecord],
    output_path: Path | str,
) -> Path:
    """Write reviews to normalized JSONL format.

    Args:
        reviews: List of ReviewRecord objects.
        output_path: Output file path.

    Returns:
        Path to written file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for review in reviews:
            for row in review.to_normalized_rows():
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return output_path


def reviews_to_aggregated_jsonl(
    reviews: list[ReviewRecord],
    output_path: Path | str,
) -> Path:
    """Write reviews to aggregated JSONL format (one row per review).

    Args:
        reviews: List of ReviewRecord objects.
        output_path: Output file path.

    Returns:
        Path to written file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for review in reviews:
            f.write(json.dumps(review.to_aggregated_row(), ensure_ascii=False) + "\n")

    return output_path


def compute_file_hash(path: Path | str) -> str:
    """Compute SHA-256 hash of a file.

    Args:
        path: Path to file.

    Returns:
        Hex digest string.
    """
    path = Path(path)
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def detect_conflicts(reviews: list[ReviewRecord]) -> list[dict[str, Any]]:
    """Detect sentiment conflicts within the same review and aspect.

    A conflict occurs when the same aspect appears with different
    sentiments in the same review.

    Args:
        reviews: List of ReviewRecord objects.

    Returns:
        List of conflict descriptions.
    """
    conflicts: list[dict[str, Any]] = []

    for review in reviews:
        aspect_sentiments: dict[str, set[str]] = defaultdict(set)
        for ann in review.annotations:
            aspect_sentiments[ann.aspect].add(ann.sentiment)

        for aspect, sentiments in aspect_sentiments.items():
            if len(sentiments) > 1:
                conflicts.append({
                    "review_id": review.review_id,
                    "aspect": aspect,
                    "sentiments": sorted(sentiments),
                    "text_preview": review.text[:80],
                })

    return conflicts
