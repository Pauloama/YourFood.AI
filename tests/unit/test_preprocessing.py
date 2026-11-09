"""Unit tests for the preprocessing module."""

from absa.preprocessing import normalize_text, compute_truncation_stats


def test_normalize_spaces_and_linebreaks():
    text = "   O   hambúrguer   estava \n\n muito  \r\n bom!   "
    normalized = normalize_text(text)
    assert normalized == "O hambúrguer estava muito bom!"


def test_preserve_accents_and_case():
    text = "Comida Épica & Deliciosa com limão e café!"
    normalized = normalize_text(text)
    assert normalized == text


def test_preserve_punctuation_and_emojis():
    text = "Pizza maravilhosa! 🍕😋 Super recomendo :)"
    normalized = normalize_text(text)
    assert normalized == text


def test_preserve_negations_and_spelling_mistakes():
    text = "Nao estava bom, o lanche veio mto ruim e cruuu."
    normalized = normalize_text(text)
    assert normalized == text


def test_compute_truncation_stats_mock_tokenizer():
    class MockTokenizer:
        def __call__(self, text, **kwargs):
            return {"input_ids": [1] * len(text.split())}

    texts = [
        "curto",
        "um texto um pouco mais longo com varias palavras para teste",
        "medio texto aqui",
    ]
    stats = compute_truncation_stats(texts, MockTokenizer(), max_length=5)
    assert stats["total_texts"] == 3
    assert stats["truncated_count"] >= 1
    assert "token_length_stats" in stats
