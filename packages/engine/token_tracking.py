"""Token aggregation helpers for chat turns."""
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, LLMResult


def _usage_values(usage) -> tuple[int, int]:
    if not usage:
        return 0, 0
    if isinstance(usage, dict):
        inp = int(usage.get("input_tokens") or 0)
        out = int(usage.get("output_tokens") or 0)
    else:
        inp = int(getattr(usage, "input_tokens", 0) or 0)
        out = int(getattr(usage, "output_tokens", 0) or 0)
    if inp == 0 and out == 0:
        total = int(
            (usage.get("total_tokens") if isinstance(usage, dict) else getattr(usage, "total_tokens", 0))
            or 0
        )
        if total > 0:
            inp = total
    return inp, out


class TurnTokenTracker(BaseCallbackHandler):
    """Accumulates tokens from every LLM call in a graph run (incl. triage)."""

    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.llm_calls = 0

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        self.llm_calls += 1
        for gen_list in response.generations:
            for gen in gen_list:
                if isinstance(gen, ChatGeneration) and gen.message:
                    meta = getattr(gen.message, "usage_metadata", None) or getattr(
                        gen.message, "response_metadata", {}
                    ).get("usage_metadata")
                    inp, out = _usage_values(meta)
                    self.input_tokens += inp
                    self.output_tokens += out
                elif hasattr(gen, "generation_info") and gen.generation_info:
                    usage = gen.generation_info.get("usage_metadata") or gen.generation_info
                    inp, out = _usage_values(usage)
                    self.input_tokens += inp
                    self.output_tokens += out


def aggregate_turn_tokens(messages: list[BaseMessage]) -> tuple[int, int, int]:
    """Sums tokens from AIMessages since the last HumanMessage."""
    t_in = t_out = 0
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            break
        if isinstance(msg, AIMessage):
            meta = getattr(msg, "usage_metadata", None)
            inp, out = _usage_values(meta)
            t_in += inp
            t_out += out
    return t_in, t_out, t_in + t_out


def resolve_turn_tokens(
    messages: list[BaseMessage],
    tracker: TurnTokenTracker,
) -> tuple[int, int, int]:
    """Prefers callback tracker totals when higher than message metadata."""
    msg_in, msg_out, msg_total = aggregate_turn_tokens(messages)
    cb_total = tracker.input_tokens + tracker.output_tokens
    if cb_total > msg_total:
        return tracker.input_tokens, tracker.output_tokens, cb_total
    return msg_in, msg_out, msg_total
