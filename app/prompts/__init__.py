from functools import lru_cache
from pathlib import Path

import yaml

_PROMPTS_PATH = Path(__file__).parent / "prompts.yaml"


@lru_cache
def _load() -> dict:
    with _PROMPTS_PATH.open() as f:
        return yaml.safe_load(f) or {}


def get(key: str) -> str:
    """Return the raw prompt at the given dotted path, e.g. ``fallbacks.llm_error``."""
    data = _load()
    for part in key.split("."):
        data = data[part]
    return data


def get_node_config(node_name: str) -> dict:
    """Return the resolved config for a node, overlaying its node_types defaults.

    Keys: node_type, model, temperature, base_persona, node_task, tools.
    """
    config = _load()
    node = config["nodes"][node_name]
    type_config = config["node_types"][node["node_type"]]
    return {
        "node_type": node["node_type"],
        "model": node.get("model", type_config["model"]),
        "temperature": node.get("temperature", type_config["temperature"]),
        "base_persona": type_config["base_persona"],
        "node_task": node.get("node_task"),
        "tools": node.get("tools", []),
    }


def get_node_prompt(node_name: str) -> str:
    """Return the composed system prompt for a node: base persona + optional task."""
    cfg = get_node_config(node_name)
    base = cfg["base_persona"].strip()
    task = (cfg["node_task"] or "").strip()
    if task:
        return f"{base}\n\n{task}"
    return base
