"""Centralized taxonomy for the ABSA pipeline.

This module is the single source of truth for aspects, entities,
sentiments, and their mappings. All other modules must import
from here instead of hardcoding values.
"""

from __future__ import annotations

import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

_DEFAULT_TAXONOMY_PATH = Path(__file__).parent.parent.parent / "configs" / "taxonomy.yaml"


@dataclass(frozen=True)
class AspectInfo:
    """Information about a single aspect."""
    code: str
    entity: str
    description: str
    examples: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Taxonomy:
    """Immutable taxonomy container."""
    version: str
    aspects: tuple[AspectInfo, ...]
    aspect_order: tuple[str, ...]
    sentiments: tuple[str, ...]
    entity_mapping: dict[str, str]

    @property
    def aspect_codes(self) -> list[str]:
        """Return list of aspect codes in canonical order."""
        return list(self.aspect_order)

    @property
    def num_aspects(self) -> int:
        return len(self.aspect_order)

    @property
    def num_sentiments(self) -> int:
        return len(self.sentiments)

    @property
    def entities(self) -> list[str]:
        """Return unique entities preserving order."""
        seen: set[str] = set()
        result: list[str] = []
        for aspect_code in self.aspect_order:
            entity = self.entity_mapping[aspect_code]
            if entity not in seen:
                seen.add(entity)
                result.append(entity)
        return result

    def get_entity(self, aspect_code: str) -> str:
        """Get entity for an aspect code. Raises ValueError if not found."""
        if aspect_code not in self.entity_mapping:
            raise ValueError(
                f"Unknown aspect '{aspect_code}'. "
                f"Valid aspects: {self.aspect_codes}"
            )
        return self.entity_mapping[aspect_code]

    def is_valid_aspect(self, aspect_code: str) -> bool:
        return aspect_code in self.entity_mapping

    def is_valid_sentiment(self, sentiment: str) -> bool:
        return sentiment in self.sentiments

    def aspect_to_index(self, aspect_code: str) -> int:
        """Return the index of an aspect in the canonical order."""
        return self.aspect_order.index(aspect_code)

    def index_to_aspect(self, index: int) -> str:
        """Return the aspect code for a given index."""
        return self.aspect_order[index]

    def get_aspect_info(self, aspect_code: str) -> AspectInfo:
        """Get full AspectInfo for a code."""
        for a in self.aspects:
            if a.code == aspect_code:
                return a
        raise ValueError(f"Unknown aspect '{aspect_code}'")

    def sentiment_to_index(self, sentiment: str) -> int:
        return self.sentiments.index(sentiment)

    def index_to_sentiment(self, index: int) -> str:
        return self.sentiments[index]


def load_taxonomy(path: Path | str | None = None) -> Taxonomy:
    """Load taxonomy from a YAML file.

    Args:
        path: Path to taxonomy YAML. Uses default if None.

    Returns:
        Immutable Taxonomy instance.
    """
    if path is None:
        path = _DEFAULT_TAXONOMY_PATH
    path = Path(path)

    with open(path, "r", encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f)

    aspect_infos: list[AspectInfo] = []
    entity_mapping: dict[str, str] = data["entity_mapping"]
    for entity_name, aspect_list in data["aspects"].items():
        for aspect_def in aspect_list:
            aspect_infos.append(AspectInfo(
                code=aspect_def["code"],
                entity=entity_mapping[aspect_def["code"]],
                description=aspect_def["description"],
                examples=aspect_def.get("examples", []),
            ))

    return Taxonomy(
        version=data["version"],
        aspects=tuple(aspect_infos),
        aspect_order=tuple(data["aspect_order"]),
        sentiments=tuple(data["sentiments"]),
        entity_mapping=entity_mapping,
    )


# Module-level singleton for convenience
_taxonomy: Taxonomy | None = None


def get_taxonomy(path: Path | str | None = None) -> Taxonomy:
    """Get or load the taxonomy singleton."""
    global _taxonomy
    if _taxonomy is None:
        _taxonomy = load_taxonomy(path)
    return _taxonomy


def reset_taxonomy() -> None:
    """Reset the taxonomy singleton (for testing)."""
    global _taxonomy
    _taxonomy = None
