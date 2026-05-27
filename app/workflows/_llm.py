"""Per-node LLM factory with cache.

Reads model + temperature from `get_node_config(node_name)` so every node's
LLM settings live in `prompts.yaml`. Instances are cached per
(model, temperature) tuple to avoid allocating a fresh client per call.
"""

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.prompts import get_node_config

_settings = get_settings()


@lru_cache
def _build_llm(model: str, temperature: float) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=_settings.openai_api_key,
    )


def llm_for_node(node_name: str) -> ChatOpenAI:
    cfg = get_node_config(node_name)
    return _build_llm(cfg["model"], cfg["temperature"])
