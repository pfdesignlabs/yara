from __future__ import annotations

from pathlib import Path
from typing import Literal, TypedDict, cast

import yaml


ContentRole = Literal["explanatory", "procedural", "support"]


class KnowledgeZonePolicy(TypedDict):
    key: str
    label: str
    user_need_summary: str
    seed_urls: list[str]
    include_url_patterns: list[str]
    exclude_url_patterns: list[str]
    content_roles: list[ContentRole]
    max_depth: int
    max_pages: int


class SourcePolicy(TypedDict):
    key: str
    label: str
    allowed_domains: list[str]
    languages: list[str]
    journeys_supported: list[str]
    zones: list[KnowledgeZonePolicy]


CONFIG_ROOT = Path(__file__).resolve().parents[2] / "config" / "knowledge"
SOURCES_CONFIG_DIR = CONFIG_ROOT / "sources"


def load_source_policies() -> list[SourcePolicy]:
    policies: list[SourcePolicy] = []

    for path in sorted(SOURCES_CONFIG_DIR.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        policies.append(cast(SourcePolicy, payload))

    return policies


SOURCE_POLICIES: list[SourcePolicy] = load_source_policies()
