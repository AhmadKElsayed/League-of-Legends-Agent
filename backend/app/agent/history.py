from langchain_core.messages import ToolMessage

# Kept small on purpose: every Send payload is serialized into the checkpoint,
# so a fan-out writes one copy of this slice per branch.
DEFAULT_WINDOW = 6

def recent_messages(messages, limit: int = DEFAULT_WINDOW) -> list:
    """The tail of the conversation, trimmed so it is still valid to send to a model.

    A naive slice can begin on a ToolMessage whose parent AIMessage was cut off,
    which providers reject as an orphaned tool result.
    """
    window = list(messages or [])[-limit:]

    start = 0
    while start < len(window) and isinstance(window[start], ToolMessage):
        start += 1

    return window[start:]
