from __future__ import annotations

from typing import TypedDict

from app.knowledge.journeys import JourneyDefinition, JourneySourceZoneMapping, load_journey_definitions
from app.knowledge.source_policies import KnowledgeZonePolicy, SourcePolicy, load_source_policies


class ResolvedJourneyZone(TypedDict):
    source: SourcePolicy
    zone: KnowledgeZonePolicy


class KnowledgeRegistry:
    def __init__(self) -> None:
        self._sources = load_source_policies()
        self._journeys = load_journey_definitions()

    def list_sources(self) -> list[SourcePolicy]:
        return self._sources

    def list_journeys(self) -> list[JourneyDefinition]:
        return self._journeys

    def get_source(self, source_key: str) -> SourcePolicy:
        for source in self._sources:
            if source["key"] == source_key:
                return source
        raise KeyError(f"Unknown source_key: {source_key}")

    def get_journey(self, journey_key: str) -> JourneyDefinition:
        for journey in self._journeys:
            if journey["key"] == journey_key:
                return journey
        raise KeyError(f"Unknown journey_key: {journey_key}")

    def get_zone(self, source_key: str, zone_key: str) -> KnowledgeZonePolicy:
        source = self.get_source(source_key)
        for zone in source["zones"]:
            if zone["key"] == zone_key:
                return zone
        raise KeyError(f"Unknown zone_key '{zone_key}' for source '{source_key}'")

    def resolve_journey_zones(self, journey_key: str) -> list[ResolvedJourneyZone]:
        journey = self.get_journey(journey_key)
        resolved: list[ResolvedJourneyZone] = []

        for mapping in journey["source_zones"]:
            resolved.extend(self._resolve_mapping(mapping))

        return resolved

    def _resolve_mapping(self, mapping: JourneySourceZoneMapping) -> list[ResolvedJourneyZone]:
        source = self.get_source(mapping["source_key"])
        resolved: list[ResolvedJourneyZone] = []

        for zone_key in mapping["zone_keys"]:
            zone = self.get_zone(source["key"], zone_key)
            resolved.append({"source": source, "zone": zone})

        return resolved


def get_registry() -> KnowledgeRegistry:
    return KnowledgeRegistry()
