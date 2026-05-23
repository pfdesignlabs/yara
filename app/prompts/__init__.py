from functools import lru_cache
from pathlib import Path

import yaml

_PROMPTS_PATH = Path(__file__).parent / "prompts.yaml"


@lru_cache
def _load() -> dict:
    with _PROMPTS_PATH.open() as f:
        return yaml.safe_load(f) or {}


def get(key: str) -> str:
    """Return the prompt at the given dotted path, e.g. ``shared.persona``."""
    data = _load()
    for part in key.split("."):
        data = data[part]
    return data
