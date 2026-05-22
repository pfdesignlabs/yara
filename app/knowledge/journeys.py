from __future__ import annotations

from pathlib import Path
from typing import TypedDict, cast

import yaml

from app.knowledge.source_policies import ContentRole


class JourneySourceZoneMapping(TypedDict):
    source_key: str
    zone_keys: list[str]


class JourneyCapability(TypedDict):
    key: str
    label: str


class GuidedJourneyFactDefinition(TypedDict, total=False):
    key: str
    label: str
    type: str
    question_key: str
    extraction_hint: str
    blocker_key: str


class GuidedJourneyRouteRule(TypedDict):
    all: dict[str, bool]
    route: str


class GuidedJourneyRouteDefinition(TypedDict, total=False):
    key: str
    label: str
    type: str
    question_key: str


class GuidedJourneyReplyVariant(TypedDict, total=False):
    key: str
    nl: str
    en: str
    uk: str


class GuidedJourneyReplyTemplates(TypedDict, total=False):
    questions: list[GuidedJourneyReplyVariant]
    routes: list[GuidedJourneyReplyVariant]


class GuidedJourneyDefinition(TypedDict, total=False):
    facts: list[GuidedJourneyFactDefinition]
    decision_order: list[str]
    route_rules: list[GuidedJourneyRouteRule]
    routes: list[GuidedJourneyRouteDefinition]
    reply_templates: GuidedJourneyReplyTemplates


class JourneyWorkflowHints(TypedDict, total=False):
    prerequisite_questions: list[str]
    guided_journey: GuidedJourneyDefinition


class JourneyDefinition(TypedDict):
    key: str
    label: str
    summary: str
    audience_notes: list[str]
    capabilities: list[JourneyCapability]
    prerequisite_topics: list[str]
    source_zones: list[JourneySourceZoneMapping]
    preferred_content_roles_by_intent: dict[str, list[ContentRole]]
    workflow_hints: JourneyWorkflowHints


CONFIG_ROOT = Path(__file__).resolve().parents[2] / "config" / "knowledge"
JOURNEYS_CONFIG_DIR = CONFIG_ROOT / "journeys"


def load_journey_definitions() -> list[JourneyDefinition]:
    journeys: list[JourneyDefinition] = []

    for path in sorted(JOURNEYS_CONFIG_DIR.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        journeys.append(cast(JourneyDefinition, payload))

    return journeys


JOURNEY_DEFINITIONS: list[JourneyDefinition] = load_journey_definitions()
