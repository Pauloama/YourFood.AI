"""Text preprocessing for the ABSA pipeline.

Follows the specification: minimal preprocessing that preserves
accents, punctuation, negation words, emojis, case, and spelling errors.
"""

from __future__ import annotations

import re


def normalize_text(text: str) -> str:
    """Apply minimal text normalization.

    Rules:
    - Convert non-string values are handled upstream (validation).
    - Normalize repeated whitespace to single space.
    - Strip leading and trailing whitespace.
    - Normalize line breaks to single space.
    - Preserve emojis.
    - Preserve case (model is cased).
    - Preserve spelling errors.
    - Preserve negation markers.
    - Do NOT remove accents.
    - Do NOT remove punctuation.
    - Do NOT apply stemming or lemmatization.

    Args:
        text: Raw review text.

    Returns:
        Normalized text.
    """
    if not isinstance(text, str):
        text = str(text)

    # Normalize line breaks to space
    text = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")

    # Normalize repeated whitespace
    text = re.sub(r"\s+", " ", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def compute_truncation_stats(
    texts: list[str],
    tokenizer,
    max_length: int = 128,
) -> dict:
    """Compute truncation statistics for a list of texts.

    Args:
        texts: List of review texts.
        tokenizer: HuggingFace tokenizer instance.
        max_length: Maximum token length.

    Returns:
        Dictionary with truncation statistics.
    """
    total = len(texts)
    truncated = 0
    lengths: list[int] = []

    for text in texts:
        encoding = tokenizer(
            text,
            truncation=False,
            add_special_tokens=True,
        )
        token_length = len(encoding["input_ids"])
        lengths.append(token_length)
        if token_length > max_length:
            truncated += 1

    truncation_rate = truncated / total if total > 0 else 0.0

    sorted_lengths = sorted(lengths)
    p50_idx = int(0.5 * len(sorted_lengths))
    p95_idx = int(0.95 * len(sorted_lengths))
    p99_idx = int(0.99 * len(sorted_lengths))

    result = {
        "total_texts": total,
        "truncated_count": truncated,
        "truncation_rate": round(truncation_rate, 4),
        "exceeds_5_percent": truncation_rate > 0.05,
        "max_length_config": max_length,
        "token_length_stats": {
            "min": min(lengths) if lengths else 0,
            "max": max(lengths) if lengths else 0,
            "mean": round(sum(lengths) / len(lengths), 1) if lengths else 0,
            "median": sorted_lengths[p50_idx] if lengths else 0,
            "p95": sorted_lengths[min(p95_idx, len(sorted_lengths) - 1)] if lengths else 0,
            "p99": sorted_lengths[min(p99_idx, len(sorted_lengths) - 1)] if lengths else 0,
        },
    }

    if result["exceeds_5_percent"]:
        result["recommendation"] = (
            f"Truncation rate ({truncation_rate:.1%}) exceeds 5%. "
            f"Consider increasing max_length to 256. "
            f"This will approximately double memory usage and increase latency."
        )

    return result
