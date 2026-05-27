"""Tool wrappers exposed to the LLM via LangChain `@tool` decorators.

Each tool wraps a service-layer call (see `app/services/`). Tools do not
know about LangGraph state — they get their own DB session per call.

`TOOL_REGISTRY` maps tool name → tool object so nodes can declare
which tools they need via the `tools:` list in `prompts.yaml`.
"""

from langchain_core.tools import BaseTool

from app.tools.action_tools import create_action, mark_action_done
from app.tools.mail_tools import draft_mail
from app.tools.reminder_tools import cancel_reminder, create_reminder

TOOL_REGISTRY: dict[str, BaseTool] = {
    "mark_action_done": mark_action_done,
    "create_action": create_action,
    "create_reminder": create_reminder,
    "cancel_reminder": cancel_reminder,
    "draft_mail": draft_mail,
}


def tools_for_node(node_name: str) -> list[BaseTool]:
    """Return the tool objects declared for a node in `prompts.yaml`.

    Raises ValueError when the node lists a tool name that is not in the
    registry — surfaces YAML typos at startup rather than at LLM-call time.
    """
    from app.prompts import get_node_config

    cfg = get_node_config(node_name)
    tool_names = cfg.get("tools") or []
    resolved: list[BaseTool] = []
    for name in tool_names:
        if name not in TOOL_REGISTRY:
            raise ValueError(
                f"Unknown tool {name!r} listed in nodes.{node_name}.tools (not in TOOL_REGISTRY)"
            )
        resolved.append(TOOL_REGISTRY[name])
    return resolved
