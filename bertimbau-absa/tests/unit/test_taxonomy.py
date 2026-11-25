"""Unit tests for the taxonomy module."""

import pytest
from absa.taxonomy import Taxonomy, get_taxonomy, load_taxonomy


def test_taxonomy_loads_correctly():
    tax = get_taxonomy()
    assert tax.version == "food-reviews-taxonomy-v1"
    assert tax.num_aspects == 12
    assert tax.num_sentiments == 3
    assert len(tax.entities) == 3


def test_aspect_codes_and_order():
    tax = get_taxonomy()
    expected_order = [
        "sabor",
        "qualidade",
        "quantidade",
        "temperatura",
        "aparencia",
        "preparo",
        "atendimento",
        "pedido_correto",
        "embalagem",
        "custo_beneficio",
        "tempo_entrega",
        "condicao_entrega",
    ]
    assert tax.aspect_codes == expected_order


def test_entity_mapping():
    tax = get_taxonomy()
    expected_mapping = {
        "sabor": "produto",
        "qualidade": "produto",
        "quantidade": "produto",
        "temperatura": "produto",
        "aparencia": "produto",
        "preparo": "produto",
        "atendimento": "loja",
        "pedido_correto": "loja",
        "embalagem": "loja",
        "custo_beneficio": "loja",
        "tempo_entrega": "entrega",
        "condicao_entrega": "entrega",
    }
    for aspect, entity in expected_mapping.items():
        assert tax.get_entity(aspect) == entity


def test_rejection_of_invalid_aspect():
    tax = get_taxonomy()
    assert not tax.is_valid_aspect("higiene")
    assert not tax.is_valid_aspect("inexistente")
    with pytest.raises(ValueError):
        tax.get_entity("higiene")


def test_sentiments():
    tax = get_taxonomy()
    assert set(tax.sentiments) == {"positivo", "negativo", "neutro"}
    assert tax.is_valid_sentiment("positivo")
    assert tax.is_valid_sentiment("negativo")
    assert tax.is_valid_sentiment("neutro")
    assert not tax.is_valid_sentiment("misto")
    assert not tax.is_valid_sentiment("bom")


def test_index_conversion():
    tax = get_taxonomy()
    for i, code in enumerate(tax.aspect_codes):
        assert tax.aspect_to_index(code) == i
        assert tax.index_to_aspect(i) == code

    for i, s in enumerate(tax.sentiments):
        assert tax.sentiment_to_index(s) == i
        assert tax.index_to_sentiment(i) == s
