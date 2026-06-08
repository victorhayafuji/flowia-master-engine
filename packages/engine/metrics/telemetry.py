"""Turn-level telemetry helpers for conversation_metrics."""
from __future__ import annotations

from collections.abc import Sequence

from langchain_core.messages import BaseMessage


def extract_turn_tools_called(messages: Sequence[BaseMessage]) -> list[str]:
    """Tool names invoked since the last human message in the thread."""
    start = 0
    for i in range(len(messages) - 1, -1, -1):
        if getattr(messages[i], "type", None) == "human":
            start = i + 1
            break

    tools: list[str] = []
    for msg in messages[start:]:
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            continue
        for call in tool_calls:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            if name:
                tools.append(str(name))
    return tools
