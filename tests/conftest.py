"""Shared test fixtures for the ABSA pipeline."""

import pytest
from pathlib import Path


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def configs_dir(project_root: Path) -> Path:
    """Return the configs directory."""
    return project_root / "configs"


@pytest.fixture
def sample_reviews() -> list[dict]:
    """Return sample review data for testing."""
    return [
        {
            "review_id": "101",
            "text": "O hambúrguer estava bom, mas chegou frio.",
            "aspect": "sabor",
            "sentiment": "positivo",
            "rating": 3,
            "user_id": "u42",
        },
        {
            "review_id": "101",
            "text": "O hambúrguer estava bom, mas chegou frio.",
            "aspect": "temperatura",
            "sentiment": "negativo",
            "rating": 3,
            "user_id": "u42",
        },
        {
            "review_id": "102",
            "text": "Demorou muito e faltou a bebida.",
            "aspect": "tempo_entrega",
            "sentiment": "negativo",
            "rating": 1,
            "user_id": "u73",
        },
        {
            "review_id": "102",
            "text": "Demorou muito e faltou a bebida.",
            "aspect": "pedido_correto",
            "sentiment": "negativo",
            "rating": 1,
            "user_id": "u73",
        },
        {
            "review_id": "103",
            "text": "Nota 1, não gostei.",
            "aspect": None,
            "sentiment": None,
        },
    ]
