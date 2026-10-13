import logging
import operator
from typing import TypedDict, Annotated, Sequence, Optional
from langchain_core.messages import BaseMessage, AIMessage

logger = logging.getLogger("lol_agent")

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # The Supervisor's dispatch plan for the current turn: [{"worker": str, "task": str}]
    plan: list[dict]

    # True when the plan holds more than one task, so workers report to the
    # Synthesizer instead of answering the user directly. Written by the
    # Supervisor on every return path — a stale True would strand a lone worker.
    fanout: bool

    # The sub-task assigned to a single worker. Only ever set through a Send
    # payload during fan-out; absent on the single-worker fast path.
    task: Optional[str]

    # Fan-out results, one entry per worker. operator.add lets concurrent
    # branches fold their writes together; the Supervisor clears it each turn
    # with langgraph.types.Overwrite([]).
    worker_results: Annotated[list[dict], operator.add]


# Markup a model emits when it wants to call a tool but none is bound — e.g.
# DeepSeek writes <|DSML|tool_calls> into the content. It is not an answer, and
# reporting it as one silently loses the data the worker already gathered.
_TOOL_MARKUP_MARKERS = ("DSML", "tool_calls>", "<tool_call", "<function_call", "<|python_tag|>")


def _looks_like_tool_markup(text: str) -> bool:
    return any(marker in text for marker in _TOOL_MARKUP_MARKERS)


def _answer_text(new_messages) -> str:
    """The worker's final prose, ignoring tool traffic."""
    for msg in reversed(list(new_messages or [])):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            content = msg.content
            if isinstance(content, list):
                # Multimodal/blocked content: keep the text parts only.
                return "\n".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                ).strip()
            text = str(content or "")
            if text and _looks_like_tool_markup(text):
                # Keep scanning back for real prose rather than handing markup on.
                logger.warning(
                    "Discarding tool-call markup emitted as content: %.120s", text
                )
                continue
            return text
    return ""


def worker_return(state, worker: str, new_messages) -> dict:
    """Build a worker's state update for whichever mode it is running in.

    Under fan-out the worker reports to the Synthesizer and writes ONLY
    worker_results: letting several workers' tool transcripts into `messages`
    would inflate the next turn's Supervisor prompt and degrade routing.
    On the single-worker fast path it answers the user directly, unchanged.

    Workers must never write `plan` or `fanout` — those are LastValue channels,
    and two concurrent writes raise InvalidUpdateError.
    """
    if state.get("fanout"):
        return {"worker_results": [{
            "worker": worker,
            "task": state.get("task") or "",
            "answer": _answer_text(new_messages),
        }]}
    return {"messages": list(new_messages or [])}
