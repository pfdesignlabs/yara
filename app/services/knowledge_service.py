from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TypedDict

from app.knowledge import get_registry

STRUCTURED_ROOT = Path("storage/knowledge/structured")
STOPWORDS = {
    "de", "het", "een", "en", "ik", "je", "jij", "u", "van", "voor", "met", "dat", "dit", "op",
    "in", "aan", "te", "is", "zijn", "om", "als", "bij", "hoe", "wat", "waar", "waarom", "kan",
    "kun", "wil", "wilt", "mijn", "uw", "your", "the", "and", "for", "with", "that", "this", "from",
}

BOOST_TERMS = {
    "activeringscode": ["activeringscode", "activeren", "code ontvangen"],
    "activeren": ["activeringscode", "activeren"],
    "aanvragen": ["aanvragen", "wat heb ik nodig", "hoe werkt het"],
    "briefadres": ["briefadres"],
    "brp": ["brp", "basisregistratie personen", "inschrijven"],
    "bsn": ["bsn", "burgerservicenummer", "inschrijven"],
    "sms": ["sms", "sms-controle", "gesproken sms"],
    "wachtwoord": ["wachtwoord"],
    "gebruikersnaam": ["gebruikersnaam"],
}

INTENT_RULES = {
    "activation_code": {
        "match_terms": ["activeringscode", "activeren", "code ontvangen"],
        "preferred_zone_keys": ["aanvragen_activeren"],
        "preferred_headings": ["DigiD activeren", "Wat heb ik nodig?", "Hoe werkt het?"],
        "dispreferred_headings": ["Nieuwe activeringscode aanvragen"],
    },
    "sms_problem": {
        "match_terms": ["sms", "sms-code", "gesproken sms"],
        "preferred_zone_keys": ["account_toegang_herstel", "aanvragen_activeren"],
        "preferred_headings": ["Sms-controle", "U kunt geen serviceberichten ontvangen", "Gebeld worden"],
        "dispreferred_headings": ["Nog geen DigiD"],
    },
    "no_bsn": {
        "match_terms": ["geen bsn", "nog geen bsn", "burgerservicenummer"],
        "preferred_zone_keys": ["inschrijven_in_den_haag", "brp_en_inschrijving", "aanvragen_activeren"],
        "preferred_headings": ["Wat heb ik nodig?", "BRP", "Inschrijving", "1e inschrijving", "Register again"],
        "dispreferred_headings": [],
    },
    "no_address": {
        "match_terms": ["geen vast adres", "briefadres", "woonadres"],
        "preferred_zone_keys": ["briefadres_en_geen_vast_adres", "briefadres_lokaal_en_contact", "aanvragen_activeren"],
        "preferred_headings": ["Briefadres", "Verschil woonadres en briefadres", "Briefadres aanvragen"],
        "dispreferred_headings": [],
    },
    "forgot_password": {
        "match_terms": ["wachtwoord vergeten", "wachtwoord kwijt", "forgot password"],
        "preferred_zone_keys": ["account_toegang_herstel"],
        "preferred_headings": ["Wachtwoord vergeten", "Lees wat u moet doen"],
        "dispreferred_headings": ["Gebruikersnaam vergeten", "Pincode vergeten"],
    },
}


class KnowledgeChunk(TypedDict):
    chunk_id: str
    source_key: str
    zone_key: str
    document_title: str | None
    document_url: str | None
    section_heading: str
    chunk_text: str


class SelectedKnowledge(TypedDict):
    journey_key: str
    chunks: list[KnowledgeChunk]


class KnowledgeService:
    def select_for_journey(
        self,
        *,
        journey_key: str,
        user_message: str | None,
        document_summary: str | None = None,
        document_journey_candidate: str | None = None,
        max_chunks: int = 4,
    ) -> SelectedKnowledge:
        registry = get_registry()
        resolved = registry.resolve_journey_zones(journey_key)
        all_chunks: list[KnowledgeChunk] = []

        for item in resolved:
            all_chunks.extend(self._load_zone_chunks(item["source"]["key"], item["zone"]["key"]))

        query = " ".join(
            part for part in [user_message or "", document_summary or "", document_journey_candidate or ""] if part
        ).strip()
        ranked = self._rank_chunks(all_chunks, query)

        if not ranked:
            ranked = all_chunks[:max_chunks]

        return {
            "journey_key": journey_key,
            "chunks": ranked[:max_chunks],
        }

    def select_for_digid_help(
        self,
        *,
        user_message: str | None,
        document_summary: str | None = None,
        document_journey_candidate: str | None = None,
        max_chunks: int = 4,
    ) -> SelectedKnowledge:
        return self.select_for_journey(
            journey_key="digid_help",
            user_message=user_message,
            document_summary=document_summary,
            document_journey_candidate=document_journey_candidate,
            max_chunks=max_chunks,
        )

    def _load_zone_chunks(self, source_key: str, zone_key: str) -> list[KnowledgeChunk]:
        zone_dir = STRUCTURED_ROOT / source_key / zone_key
        chunks: list[KnowledgeChunk] = []

        for path in sorted(zone_dir.glob("doc_*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            chunks.extend(payload)

        return chunks

    def _rank_chunks(self, chunks: list[KnowledgeChunk], query: str) -> list[KnowledgeChunk]:
        query_terms = self._tokenize(query)
        if not query_terms:
            return chunks

        scored: list[tuple[int, KnowledgeChunk]] = []
        boost_terms = self._expand_terms(query_terms)
        intent_rule = self._match_intent_rule(query.lower())

        for chunk in chunks:
            heading = (chunk.get("section_heading", "") or "").lower()
            title = (chunk.get("document_title", "") or "").lower()
            text = (chunk.get("chunk_text", "") or "").lower()
            zone_key = (chunk.get("zone_key", "") or "").lower()
            haystack = " ".join([heading, title, text, zone_key])

            score = 0
            for term in query_terms:
                if term in heading:
                    score += 5
                elif term in title:
                    score += 4
                elif term in zone_key:
                    score += 3
                elif term in haystack:
                    score += 1

            for term in boost_terms:
                if term in heading:
                    score += 4
                elif term in title:
                    score += 3
                elif term in haystack:
                    score += 1

            if intent_rule:
                if chunk.get("zone_key") in intent_rule["preferred_zone_keys"]:
                    score += 6
                if any(pref.lower() in heading for pref in intent_rule["preferred_headings"]):
                    score += 6
                if any(bad.lower() in heading for bad in intent_rule["dispreferred_headings"]):
                    score -= 5

            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored]

    def _expand_terms(self, query_terms: list[str]) -> list[str]:
        expanded: list[str] = []
        for term in query_terms:
            expanded.extend(BOOST_TERMS.get(term, []))
        return expanded

    def _match_intent_rule(self, query: str) -> dict | None:
        for rule in INTENT_RULES.values():
            if any(term in query for term in rule["match_terms"]):
                return rule
        return None

    def _tokenize(self, text: str) -> list[str]:
        terms = re.findall(r"[a-zA-Z0-9_\-]+", text.lower())
        return [term for term in terms if len(term) > 2 and term not in STOPWORDS]


def format_selected_knowledge(selected: SelectedKnowledge) -> str:
    if not selected["chunks"]:
        return ""

    lines = ["Gebruik deze betrouwbare kennis alleen als hij echt past bij het bericht van de gebruiker:"]
    for chunk in selected["chunks"]:
        lines.append(
            f"- [{chunk['source_key']}/{chunk['zone_key']}] {chunk['section_heading']}: {chunk['chunk_text']}"
        )
    return "\n".join(lines)
