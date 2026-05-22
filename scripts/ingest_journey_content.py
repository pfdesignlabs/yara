from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.knowledge import get_registry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest all source zones linked to a journey.")
    parser.add_argument("journey_key", help="Journey key, e.g. 'digid_help'")
    parser.add_argument("--base-url", default="http://localhost:3002", help="Firecrawl base URL")
    parser.add_argument("--dry-run", action="store_true", help="Only print the zones that would be ingested")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    registry = get_registry()
    resolved = registry.resolve_journey_zones(args.journey_key)

    if args.dry_run:
        for item in resolved:
            print(f"{item['source']['key']}:{item['zone']['key']}")
        return

    script_path = PROJECT_ROOT / "scripts" / "ingest_source_content.py"

    for item in resolved:
        command = [
            sys.executable,
            str(script_path),
            item["source"]["key"],
            "--zone-key",
            item["zone"]["key"],
            "--base-url",
            args.base_url,
        ]
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
