from __future__ import annotations

from app.knowledge import get_registry


class GuidedJourneyService:
    def get_guided_journey(self, journey_key: str) -> dict | None:
        journey = get_registry().get_journey(journey_key)
        return (journey.get("workflow_hints") or {}).get("guided_journey")

    def decide_route(self, *, journey_key: str, facts: dict[str, object]) -> str:
        config = self.get_guided_journey(journey_key) or {}
        for rule in config.get("route_rules", []):
            conditions = rule.get("all", {})
            if all(facts.get(key) is value for key, value in conditions.items()):
                return rule["route"]
        return "collect_more_context"

    def next_question_key(self, *, journey_key: str, facts: dict[str, object]) -> str | None:
        config = self.get_guided_journey(journey_key) or {}
        fact_defs = {item["key"]: item for item in config.get("facts", [])}
        for fact_key in config.get("decision_order", []):
            if facts.get(fact_key) is None:
                fact_def = fact_defs.get(fact_key)
                if fact_def:
                    return fact_def.get("question_key")
        return None

    def fact_definitions(self, *, journey_key: str) -> list[dict]:
        config = self.get_guided_journey(journey_key) or {}
        return config.get("facts", [])

    def render_template(self, *, journey_key: str, template_group: str, template_key: str, language: str) -> str | None:
        config = self.get_guided_journey(journey_key) or {}
        templates = (config.get("reply_templates") or {}).get(template_group, [])
        for item in templates:
            if item.get("key") == template_key:
                return item.get(language) or item.get("nl")
        return None
