"""Knowledge-base scraper — pulls the watchlist sources into workspace/.../raw/.

Reads `workspace/knowledge/watchlist.yaml`, scrapes (or crawls) each due source
via the Firecrawl API, and writes clean markdown into the source's category
`raw/` folder with a raw frontmatter (trust: to-validate) — so every scrape
lands behind the validation gate by default.

    python scripts/knowledge/scrape.py                 # all due sources
    python scripts/knowledge/scrape.py --source "Nibud" # one source
    python scripts/knowledge/scrape.py --force          # ignore the interval
    python scripts/knowledge/scrape.py --dry-run        # show what would run

Cloud by default; point at a self-hosted instance with
FIRECRAWL_API_URL=http://localhost:8080/v2. Needs FIRECRAWL_API_KEY in .env.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import yaml

_REPO = Path(__file__).resolve().parents[2]
_WORKSPACE = _REPO / "workspace"
_WATCHLIST = _WORKSPACE / "knowledge" / "watchlist.yaml"
_STATE = _WORKSPACE / "knowledge" / ".scrape_state.json"

_INTERVALS = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    "monthly": timedelta(days=30),
}
_CRAWL_TIMEOUT_S = 180
_POLL_EVERY_S = 4
_MAX_RETRIES = 4
_BACKOFF_BASE_S = 15


def _env(key: str) -> str | None:
    line = next(
        (line for line in (_REPO / ".env").read_text().splitlines() if line.startswith(f"{key}=")),
        None,
    )
    return line.split("=", 1)[1].strip() if line else None


def _slug(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-") or "page"


def _frontmatter(source: str, url: str, category: str) -> str:
    today = datetime.now(UTC).date().isoformat()
    return (
        f"---\nsource: {source}\nurl: {url}\ncategory: {category}\n"
        f"scraped: {today}\ntrust: to-validate\nvia: firecrawl\n---\n\n"
    )


class Firecrawl:
    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"}, timeout=httpx.Timeout(60.0)
        )

    def _post(self, path: str, payload: dict) -> httpx.Response:
        # The cloud free tier rate-limits crawl jobs hard; back off and retry on 429.
        r = None
        for attempt in range(_MAX_RETRIES):
            r = self._client.post(f"{self._base}{path}", json=payload)
            if r.status_code != 429:
                r.raise_for_status()
                return r
            wait = int(r.headers.get("retry-after") or 0) or _BACKOFF_BASE_S * 2**attempt
            print(
                f"  · 429 rate-limited; waiting {wait}s (try {attempt + 1}/{_MAX_RETRIES})",
                file=sys.stderr,
            )
            time.sleep(wait)
        r.raise_for_status()
        return r

    def scrape(self, url: str) -> list[tuple[str, str]]:
        r = self._post("/scrape", {"url": url, "formats": ["markdown"]})
        data = r.json().get("data", {}) or {}
        md = data.get("markdown") or ""
        page_url = (data.get("metadata") or {}).get("sourceURL") or url
        return [(page_url, md)] if md else []

    def crawl(self, url: str, limit: int) -> list[tuple[str, str]]:
        start = self._post("/crawl", {"url": url, "limit": limit})
        job_id = start.json().get("id")
        if not job_id:
            return []
        deadline = time.monotonic() + _CRAWL_TIMEOUT_S
        while time.monotonic() < deadline:
            time.sleep(_POLL_EVERY_S)
            poll = self._client.get(f"{self._base}/crawl/{job_id}")
            poll.raise_for_status()
            body = poll.json()
            if body.get("status") == "completed":
                pages = []
                for item in body.get("data", []) or []:
                    md = item.get("markdown") or ""
                    page_url = (item.get("metadata") or {}).get("sourceURL") or url
                    if md and not page_url.rstrip("/").endswith(".xml"):
                        pages.append((page_url, md))
                return pages
        print(f"  ! crawl timed out after {_CRAWL_TIMEOUT_S}s", file=sys.stderr)
        return []


def _is_due(name: str, interval: str, state: dict, force: bool) -> bool:
    if force:
        return True
    last = state.get(name)
    if not last:
        return True
    delta = _INTERVALS.get(interval, _INTERVALS["weekly"])
    return datetime.now(UTC) - datetime.fromisoformat(last) >= delta


def _write(category: str, source: str, source_slug: str, pages: list[tuple[str, str]]) -> int:
    out_dir = _WORKSPACE / "knowledge" / category / "raw" / source_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    for page_url, md in pages:
        name = _slug(page_url.split("//", 1)[-1]) + ".md"
        (out_dir / name).write_text(_frontmatter(source, page_url, category) + md)
    return len(pages)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape watchlist sources into the knowledge base")
    parser.add_argument("--source", help="only this source (by name, substring match)")
    parser.add_argument("--force", action="store_true", help="ignore the per-source interval")
    parser.add_argument(
        "--dry-run", action="store_true", help="show what would run, scrape nothing"
    )
    args = parser.parse_args()

    config = yaml.safe_load(_WATCHLIST.read_text())
    defaults = config.get("defaults", {})
    sources = config.get("sources", [])
    state = json.loads(_STATE.read_text()) if _STATE.exists() else {}

    api_key = _env("FIRECRAWL_API_KEY")
    if not api_key:
        sys.exit("FIRECRAWL_API_KEY not set in .env")
    base_url = _env("FIRECRAWL_API_URL") or "https://api.firecrawl.dev/v2"
    fc = Firecrawl(base_url, api_key)

    for src in sources:
        name = src["name"]
        if args.source and args.source.lower() not in name.lower():
            continue
        interval = src.get("interval", defaults.get("interval", "weekly"))
        if not _is_due(name, interval, state, args.force):
            print(f"- skip (not due, {interval}): {name}")
            continue
        mode = src.get("mode", defaults.get("mode", "scrape"))
        print(f"→ {mode}: {name}")
        if args.dry_run:
            continue
        try:
            pages = (
                fc.crawl(src["url"], src.get("limit", 25))
                if mode == "crawl"
                else fc.scrape(src["url"])
            )
            n = _write(src["category"], name, _slug(name), pages)
            state[name] = datetime.now(UTC).isoformat()
            print(f"  ✓ {n} page(s) → knowledge/{src['category']}/raw/{_slug(name)}/")
        except Exception as exc:  # noqa: BLE001 — one bad source must not stop the run
            print(f"  ! failed: {exc}", file=sys.stderr)

    if not args.dry_run:
        _STATE.write_text(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
