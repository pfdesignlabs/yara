"""LLM refine — turn raw scrapes into DRAFT refined extracts (still to-validate).

Reads raw markdown under `workspace/knowledge/<cat>/raw/<slug>/`, asks an LLM to
strip navigation/boilerplate and distil the relevant content, and writes a draft
`workspace/knowledge/<cat>/refined/<slug>/<page>.md` with `trust: to-validate`.

This is only a head start — you still read the draft and bump `trust: validated`
yourself. It NEVER overwrites a refined file you've already marked `validated`.

    python scripts/knowledge/refine.py                 # all raw missing a refined
    python scripts/knowledge/refine.py --source Nibud  # one source (substring)
    python scripts/knowledge/refine.py --force         # re-refine to-validate drafts
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from app.core.config import get_settings  # noqa: E402
from app.prompts import get_node_config  # noqa: E402

_KNOWLEDGE = _REPO / "workspace" / "knowledge"
_OBJECTIVE = _REPO / "workspace" / "objective.md"

_SYSTEM = """Je schoont een ruwe webscrape op tot een bruikbaar kennis-extract voor een
aanbestedings-kennisbank (schuldhulp & nieuwkomers, Den Haag).

- Verwijder navigatie, menu's, cookie-meldingen, footers, knoppen en herhaalde boilerplate.
- Behoud de inhoudelijke kern: feiten, cijfers, data, namen, deadlines, beleid, citaten.
- Structureer met korte kopjes en bullets waar dat helpt; vat samen, maar verzin niets
  en laat geen relevante cijfers/data weg.
- Sluit AF met een sectie `## Relatie tot ons doel` (max 3-4 zinnen): hoe draagt deze bron
  bij aan, of wat betekent zij voor, het doel hieronder? Wees concreet en eerlijk — als de
  bron nauwelijks relevant is, zeg dat.
- Antwoord in het Nederlands, alleen de opgeschoonde markdown (geen inleiding over wat je deed).

--- ONS DOEL (context, niet overnemen in het extract) ---
{objective}
--- EINDE DOEL ---"""


def _split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    _, fm, body = text.split("---\n", 2)
    meta = {}
    for line in fm.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, body.lstrip("\n")


def _is_validated(path: Path) -> bool:
    if not path.exists():
        return False
    meta, _ = _split_frontmatter(path.read_text())
    return meta.get("trust") == "validated"


def _frontmatter(meta: dict, model: str) -> str:
    today = datetime.now(UTC).date().isoformat()
    return (
        f"---\nsource: {meta.get('source', '')}\nurl: {meta.get('url', '')}\n"
        f"category: {meta.get('category', '')}\nscraped: {meta.get('scraped', '')}\n"
        f"trust: to-validate\nrefined_by: llm:{model}\nrefined_on: {today}\n"
        f"validated_by:\nvalidated_on:\nnote:\n---\n\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM-refine raw scrapes into draft refined extracts"
    )
    parser.add_argument("--source", help="only raw under a slug matching this (substring)")
    parser.add_argument(
        "--force", action="store_true", help="re-refine even if a to-validate draft exists"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="list what would be refined, call no LLM"
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.openai_api_key:
        sys.exit("OPENAI_API_KEY not set in .env")
    cfg = get_node_config("state_extractor_node")
    model = cfg["model"]
    llm = ChatOpenAI(model=model, temperature=cfg["temperature"], api_key=settings.openai_api_key)

    objective = _OBJECTIVE.read_text() if _OBJECTIVE.exists() else "(geen doel gedefinieerd)"
    system = _SYSTEM.format(objective=objective)

    raw_files = sorted(_KNOWLEDGE.glob("*/raw/*/*.md"))
    for raw in raw_files:
        slug = raw.parent.name
        if args.source and args.source.lower() not in slug.lower():
            continue
        refined = Path(str(raw).replace("/raw/", "/refined/", 1))
        if _is_validated(refined):
            print(f"- skip (validated, never overwrite): {refined.relative_to(_KNOWLEDGE)}")
            continue
        if refined.exists() and not args.force:
            print(f"- skip (draft exists, use --force): {refined.relative_to(_KNOWLEDGE)}")
            continue
        print(f"→ refine: {raw.relative_to(_KNOWLEDGE)}")
        if args.dry_run:
            continue
        meta, body = _split_frontmatter(raw.read_text())
        try:
            response = llm.invoke([SystemMessage(content=system), HumanMessage(content=body)])
            extract = (
                response.content if isinstance(response.content, str) else str(response.content)
            )
            refined.parent.mkdir(parents=True, exist_ok=True)
            refined.write_text(_frontmatter(meta, model) + extract.strip() + "\n")
            print(f"  ✓ draft → {refined.relative_to(_KNOWLEDGE)} (trust: to-validate)")
        except Exception as exc:  # noqa: BLE001 — one bad file must not stop the run
            print(f"  ! failed: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
