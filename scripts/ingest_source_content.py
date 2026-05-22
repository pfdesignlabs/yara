from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.knowledge.source_policies import SourcePolicy, load_source_policies

FIRECRAWL_BASE_URL = "http://localhost:3002"
RAW_OUTPUT_ROOT = Path("storage/knowledge/raw")
NORMALIZED_OUTPUT_ROOT = Path("storage/knowledge/normalized")


@dataclass
class SelectedZone:
    source_key: str
    source_label: str
    zone: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest raw source content using source policies.")
    parser.add_argument("source_key", help="Source policy key, e.g. 'digid'")
    parser.add_argument("--zone-key", help="Optional zone key to ingest only one zone")
    parser.add_argument("--base-url", default=FIRECRAWL_BASE_URL, help="Firecrawl base URL")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = get_source_policy(args.source_key)
    zones = select_zones(source, args.zone_key)

    with httpx.Client(base_url=args.base_url, timeout=120.0) as client:
        for selected_zone in zones:
            ingest_zone(client, selected_zone)


def get_source_policy(source_key: str) -> SourcePolicy:
    for policy in load_source_policies():
        if policy["key"] == source_key:
            return policy
    available = ", ".join(policy["key"] for policy in SOURCE_POLICIES)
    raise SystemExit(f"Unknown source_key '{source_key}'. Available: {available}")


def select_zones(source: SourcePolicy, zone_key: str | None) -> list[SelectedZone]:
    zones = source["zones"]
    if zone_key is not None:
        zones = [zone for zone in zones if zone["key"] == zone_key]
        if not zones:
            available = ", ".join(zone["key"] for zone in source["zones"])
            raise SystemExit(f"Unknown zone_key '{zone_key}' for source '{source['key']}'. Available: {available}")

    return [
        SelectedZone(
            source_key=source["key"],
            source_label=source["label"],
            zone=zone,
        )
        for zone in zones
    ]


def ingest_zone(client: httpx.Client, selected_zone: SelectedZone) -> None:
    zone = selected_zone.zone
    zone_output_dir = RAW_OUTPUT_ROOT / selected_zone.source_key / zone["key"]
    zone_output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "source_key": selected_zone.source_key,
        "source_label": selected_zone.source_label,
        "zone_key": zone["key"],
        "zone_label": zone["label"],
        "user_need_summary": zone["user_need_summary"],
        "content_roles": zone["content_roles"],
        "include_url_patterns": zone["include_url_patterns"],
        "exclude_url_patterns": zone["exclude_url_patterns"],
        "seed_urls": zone["seed_urls"],
        "max_depth": zone["max_depth"],
        "max_pages": zone["max_pages"],
        "ingested_at": now_iso(),
        "documents": [],
        "discovered_urls": [],
    }

    seen_urls: set[str] = set()
    candidate_urls: list[str] = []

    for seed_url in zone["seed_urls"]:
        candidate_urls.append(seed_url)
        for discovered_url in discover_links(client, seed_url):
            if url_matches_zone(discovered_url, selected_zone):
                candidate_urls.append(discovered_url)

    filtered_urls: list[str] = []
    for url in candidate_urls:
        normalized_url = normalize_url(url)
        if normalized_url in seen_urls:
            continue
        if not url_matches_zone(normalized_url, selected_zone):
            continue
        seen_urls.add(normalized_url)
        filtered_urls.append(normalized_url)

    filtered_urls = filtered_urls[: zone["max_pages"]]
    manifest["discovered_urls"] = filtered_urls

    for index, target_url in enumerate(filtered_urls, start=1):
        response_json = scrape_url(client, target_url)
        filename = f"doc_{index:02d}.json"
        file_path = zone_output_dir / filename
        file_path.write_text(json.dumps(response_json, indent=2, ensure_ascii=False))

        manifest["documents"].append(
            {
                "url": target_url,
                "file": str(file_path.relative_to(RAW_OUTPUT_ROOT.parent)),
                "success": response_json.get("success", False),
                "title": (((response_json.get("data") or {}).get("metadata") or {}).get("title")),
                "source_url": (((response_json.get("data") or {}).get("metadata") or {}).get("sourceURL")),
            }
        )

    manifest_path = zone_output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    normalize_zone_output(selected_zone, manifest)
    print(f"Ingested {selected_zone.source_key}/{zone['key']} -> {manifest_path}")


def discover_links(client: httpx.Client, seed_url: str) -> list[str]:
    response = client.post(
        "/v2/map",
        json={
            "url": seed_url,
        },
    )
    response.raise_for_status()
    payload = response.json()
    links = payload.get("links", [])
    urls: list[str] = []
    for item in links:
        if isinstance(item, dict):
            url = item.get("url")
            if url:
                urls.append(url)
        elif isinstance(item, str):
            urls.append(item)
    return urls


def url_matches_zone(url: str, selected_zone: SelectedZone) -> bool:
    zone = selected_zone.zone
    parsed = urlparse(url)

    if parsed.netloc not in {domain.lower() for domain in get_allowed_domains(selected_zone)}:
        return False

    for blocked_fragment in zone["exclude_url_patterns"]:
        if blocked_fragment in url:
            return False

    include_patterns = zone["include_url_patterns"]
    if include_patterns and not any(fragment in parsed.path for fragment in include_patterns):
        seed_paths = {urlparse(seed).path for seed in zone["seed_urls"]}
        if parsed.path not in seed_paths:
            return False

    return True


def get_allowed_domains(selected_zone: SelectedZone) -> list[str]:
    source = get_source_policy(selected_zone.source_key)
    return source["allowed_domains"]


def normalize_url(url: str) -> str:
    return re.sub(r"#.*$", "", url).rstrip("/") or url


def normalize_zone_output(selected_zone: SelectedZone, raw_manifest: dict[str, Any]) -> None:
    zone = selected_zone.zone
    normalized_dir = NORMALIZED_OUTPUT_ROOT / selected_zone.source_key / zone["key"]
    normalized_dir.mkdir(parents=True, exist_ok=True)

    normalized_manifest = {
        "source_key": raw_manifest["source_key"],
        "zone_key": raw_manifest["zone_key"],
        "zone_label": raw_manifest["zone_label"],
        "normalized_at": now_iso(),
        "documents": [],
    }

    for index, document in enumerate(raw_manifest["documents"], start=1):
        raw_file = RAW_OUTPUT_ROOT.parent / document["file"]
        raw_payload = json.loads(raw_file.read_text())
        markdown = ((raw_payload.get("data") or {}).get("markdown") or "").strip()
        metadata = ((raw_payload.get("data") or {}).get("metadata") or {})
        markdown = clean_markdown(markdown, metadata)

        markdown_filename = f"doc_{index:02d}.md"
        markdown_path = normalized_dir / markdown_filename
        markdown_path.write_text(markdown + "\n", encoding="utf-8")

        normalized_manifest["documents"].append(
            {
                "url": document["url"],
                "title": document.get("title"),
                "source_url": document.get("source_url"),
                "markdown_file": str(markdown_path.relative_to(NORMALIZED_OUTPUT_ROOT.parent)),
                "language": metadata.get("language"),
                "status_code": metadata.get("statusCode"),
            }
        )

    manifest_path = normalized_dir / "manifest.json"
    manifest_path.write_text(json.dumps(normalized_manifest, indent=2, ensure_ascii=False))


def clean_markdown(markdown: str, metadata: dict[str, Any] | None = None) -> str:
    lines = [line.rstrip() for line in markdown.splitlines()]
    metadata = metadata or {}

    if len(lines) >= 2 and lines[0].strip() == "main.content" and set(lines[1].strip()) == {"-"}:
        lines = lines[2:]

    lines = strip_leading_boilerplate(lines, metadata)

    cleaned: list[str] = []
    previous_normalized: str | None = None
    index = 0

    while index < len(lines):
        line = lines[index]
        normalized = re.sub(r"\s+", " ", line).strip()
        next_line = lines[index + 1] if index + 1 < len(lines) else None
        next_next_line = lines[index + 2] if index + 2 < len(lines) else None
        next_normalized = re.sub(r"\s+", " ", next_line).strip() if next_line is not None else None

        if not normalized:
            cleaned.append("")
            index += 1
            continue

        if is_noise_line(normalized):
            index += 1
            continue

        if previous_normalized and normalized == previous_normalized:
            index += 1
            continue

        if (
            normalized
            and next_line is not None
            and next_next_line is not None
            and next_normalized == normalized
            and set(next_next_line.strip()) in ({"-"}, {"="})
        ):
            cleaned.append(line)
            previous_normalized = normalized
            index += 3
            continue

        cleaned.append(line)
        previous_normalized = normalized
        index += 1

    text = "\n".join(cleaned)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_leading_boilerplate(lines: list[str], metadata: dict[str, Any]) -> list[str]:
    title_candidates = [
        metadata.get("Pagina_Naam"),
        metadata.get("ogTitle"),
        metadata.get("title"),
    ]

    for candidate in title_candidates:
        if not candidate:
            continue
        candidate = str(candidate).strip()
        candidate = candidate.removesuffix(" - Den Haag").removesuffix(" - The Hague").strip()
        for index, line in enumerate(lines):
            normalized = re.sub(r"\s+", " ", line).strip()
            if normalized == candidate:
                return lines[index:]

    return lines


def is_noise_line(normalized: str) -> bool:
    lowered = normalized.lower()
    if normalized.startswith("![") and "base64-image-removed" in lowered:
        return True
    if normalized.startswith("[]("):
        return True
    if lowered in {
        "toestemming",
        "details",
        "over",
        "toestemmingsselectie",
        "cookies toestaan",
        "weigeren selectie toestaan aanpassen",
        "meldingen",
    }:
        return True
    if lowered.startswith("cookies en privacy op denhaag.nl"):
        return True
    if lowered.startswith("[#") or lowered.startswith("\\[#"):
        return True
    if "cookiebot" in lowered:
        return True
    if "gpc_banner_icon" in lowered or "gpc_toast_text" in lowered:
        return True
    if lowered.startswith("[luister](https://app-eu.readspeaker.com/"):
        return True
    return False


def scrape_url(client: httpx.Client, url: str) -> dict[str, Any]:
    response = client.post(
        "/v2/scrape",
        json={
            "url": url,
            "formats": ["markdown"],
        },
    )
    response.raise_for_status()
    return response.json()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    main()
