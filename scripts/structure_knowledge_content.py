from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.knowledge import get_registry

NORMALIZED_ROOT = Path("storage/knowledge/normalized")
STRUCTURED_ROOT = Path("storage/knowledge/structured")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Structure normalized knowledge docs into sections/chunks.")
    parser.add_argument("journey_key", help="Journey key, e.g. 'digid_help'")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    registry = get_registry()
    resolved = registry.resolve_journey_zones(args.journey_key)

    for item in resolved:
        structure_zone(item["source"]["key"], item["zone"]["key"])


def structure_zone(source_key: str, zone_key: str) -> None:
    normalized_dir = NORMALIZED_ROOT / source_key / zone_key
    manifest_path = normalized_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"Missing normalized manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    structured_dir = STRUCTURED_ROOT / source_key / zone_key
    structured_dir.mkdir(parents=True, exist_ok=True)

    zone_chunks: list[dict[str, Any]] = []

    for doc_index, document in enumerate(manifest["documents"], start=1):
        markdown_file = NORMALIZED_ROOT.parent / document["markdown_file"]
        markdown = markdown_file.read_text(encoding="utf-8")
        sections = split_into_sections(markdown)

        doc_chunks = []
        for section_index, section in enumerate(sections, start=1):
            chunk = {
                "chunk_id": f"{source_key}:{zone_key}:doc{doc_index:02d}:sec{section_index:02d}",
                "source_key": source_key,
                "zone_key": zone_key,
                "document_title": document.get("title"),
                "document_url": document.get("source_url") or document.get("url"),
                "section_heading": section["heading"],
                "chunk_text": section["text"],
            }
            doc_chunks.append(chunk)
            zone_chunks.append(chunk)

        output_path = structured_dir / f"doc_{doc_index:02d}.json"
        output_path.write_text(json.dumps(doc_chunks, indent=2, ensure_ascii=False), encoding="utf-8")

    zone_manifest = {
        "source_key": source_key,
        "zone_key": zone_key,
        "chunk_count": len(zone_chunks),
        "documents": len(manifest["documents"]),
        "files": [f"doc_{index:02d}.json" for index in range(1, len(manifest["documents"]) + 1)],
    }
    (structured_dir / "manifest.json").write_text(json.dumps(zone_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Structured {source_key}/{zone_key} -> {structured_dir / 'manifest.json'}")


def split_into_sections(markdown: str) -> list[dict[str, str]]:
    lines = markdown.splitlines()
    sections: list[dict[str, str]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_heading, current_lines
        text = "\n".join(line.rstrip() for line in current_lines).strip()
        if text:
            sections.append(
                {
                    "heading": current_heading or "Introduction",
                    "text": text,
                }
            )
        current_lines = []

    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        next_line = lines[index + 1].rstrip() if index + 1 < len(lines) else None

        if line.strip() and next_line and set(next_line.strip()) in ({"="}, {"-"}):
            flush()
            current_heading = line.strip()
            index += 2
            continue

        if re.match(r"^#{2,6}\s+", line.strip()):
            flush()
            current_heading = re.sub(r"^#{2,6}\s+", "", line.strip())
            index += 1
            continue

        current_lines.append(line)
        index += 1

    flush()
    return merge_small_sections(sections)


def merge_small_sections(sections: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []

    for section in sections:
        text = section["text"].strip()
        if not merged:
            merged.append(section)
            continue

        if len(text) < 180:
            merged[-1]["text"] = (merged[-1]["text"].rstrip() + "\n\n" + (section["heading"] + "\n" + text).strip()).strip()
            continue

        merged.append(section)

    return merged


if __name__ == "__main__":
    main()
