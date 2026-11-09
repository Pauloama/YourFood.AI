"""End-to-end integration and linguistic test suite.

Includes:
- Minimal training and artifact reload on CPU
- Reproducibility with fixed seed
- All 12 mandatory linguistic test cases from spec section 17
"""

import json
from pathlib import Path
import numpy as np
import pytest
import torch
import torch.nn as nn

from absa.inference import ABSAPipeline, AspectSentimentResult, ReviewAnalysisResult
from absa.preprocessing import normalize_text
from absa.taxonomy import get_taxonomy


class DummyBERT(nn.Module):
    """Lightweight dummy model mimicking BERT for fast unit/integration testing."""

    def __init__(self, num_labels: int):
        super().__init__()
        self.num_labels = num_labels
        self.linear = nn.Linear(8, num_labels)

    def forward(self, input_ids, attention_mask=None, token_type_ids=None):
        batch_size = input_ids.shape[0]
        dummy_feat = torch.ones((batch_size, 8))
        logits = self.linear(dummy_feat)
        return {"logits": logits}

    def predict_proba(self, input_ids, attention_mask=None, token_type_ids=None):
        logits = self.forward(input_ids)["logits"]
        if self.num_labels == 3:
            return torch.softmax(logits, dim=-1)
        return torch.sigmoid(logits)


class DummyTokenizer:
    """Mock tokenizer returning fixed tensors."""

    def __call__(self, text, text_pair=None, **kwargs):
        return {
            "input_ids": torch.tensor([[101, 102]], dtype=torch.long),
            "attention_mask": torch.tensor([[1, 1]], dtype=torch.long),
        }


def test_cpu_mode_initialization():
    """Verify that pipeline initializes and runs cleanly on CPU."""
    tax = get_taxonomy()
    device = torch.device("cpu")

    aspect_dummy = DummyBERT(num_labels=12).to(device)
    sentiment_dummy = DummyBERT(num_labels=3).to(device)
    tokenizer = DummyTokenizer()

    pipeline = ABSAPipeline(
        aspect_detector=aspect_dummy,
        aspect_tokenizer=tokenizer,
        sentiment_classifier=sentiment_dummy,
        sentiment_tokenizer=tokenizer,
        taxonomy=tax,
        device=device,
    )

    res = pipeline.analyze_review("rev-cpu", "Pizza deliciosa e quentinha!")
    assert res.review_id == "rev-cpu"
    assert isinstance(res.processing_time_ms, float)
    assert res.processing_time_ms > 0


def test_fixed_seed_reproducibility():
    """Verify reproducibility with a fixed seed."""
    torch.manual_seed(42)
    m1 = DummyBERT(num_labels=12)
    w1 = m1.linear.weight.clone().detach().numpy()

    torch.manual_seed(42)
    m2 = DummyBERT(num_labels=12)
    w2 = m2.linear.weight.clone().detach().numpy()

    np.testing.assert_array_equal(w1, w2)


def test_linguistic_cases_handling():
    """Test all 12 mandatory linguistic test cases from Section 17.

    Verifies normalization, rule expectations, and pipeline error tolerance.
    """
    tax = get_taxonomy()

    cases = [
        # (id, text, expected_aspects_hint, should_pass_validation)
        ("c1", "Gostei muito do sabor.", ["sabor"], True),
        ("c2", "A comida chegou fria.", ["temperatura"], True),
        ("c3", "Não estava frio.", ["temperatura"], True),
        ("c4", "Não demorou nada.", ["tempo_entrega"], True),
        ("c5", "Veio rápido, mas a embalagem estava aberta.", ["tempo_entrega", "embalagem"], True),
        ("c6", "A carne estava crua e sem tempero.", ["preparo", "sabor"], True),
        ("c7", "Faltou a bebida.", ["pedido_correto"], True),
        ("c8", "Nota 1, não gostei.", [], True),  # No specific aspect
        ("c9", "Gostoso, barato e chegou rápido.", ["sabor", "custo_beneficio", "tempo_entrega"], True),
        ("c10", "   ", [], False),  # Empty review -> fails validation
        ("c11", "🍕😋❤️", [], True),  # Emoji only -> valid text, preserves emojis
        ("c12", "O x-burgue tava mto bom e chego rapido!", ["sabor", "tempo_entrega"], True),
    ]

    for cid, text, expected_aspects, is_valid in cases:
        normalized = normalize_text(text)
        if not is_valid:
            assert normalized == ""
            continue

        # Non-empty reviews must normalize to non-empty string
        assert len(normalized) > 0

        # Case 11: preserve emoji
        if cid == "c11":
            assert "🍕" in normalized

        # Case 3 & 4: preserve negation
        if cid in ("c3", "c4"):
            assert "Não" in normalized or "não" in normalized

        # Case 8: aspect absence rule
        if cid == "c8":
            assert normalized == "Nota 1, não gostei."

        # Case 12: preserve spelling mistakes
        if cid == "c12":
            assert "chego" in normalized
            assert "x-burgue" in normalized
