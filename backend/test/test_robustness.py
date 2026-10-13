import pytest
from unittest.mock import patch, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.types import Overwrite
from app.agent.nodes.supervisor import supervisor_node, _normalize, SubTask, Plan
from app.agent.llm import invoke_with_retry
from app.agent.state import worker_return
from app.agent.history import recent_messages
from app.agent.prompts import with_subtask


def _plan(*pairs):
    return [SubTask(worker=w, task=t) for w, t in pairs]


# --- Supervisor -------------------------------------------------------------

def _stub_chain():
    """Replace the whole supervisor chain. Patching `.ainvoke` on it does not
    work: it is a pydantic RunnableSequence and the attribute cannot be unset."""
    return patch("app.agent.nodes.supervisor.supervisor_chain", new_callable=AsyncMock)


@pytest.mark.asyncio
async def test_supervisor_fallback_on_error():
    """If the LLM chain fails, the supervisor safely routes to the GeneralAgent."""
    with _stub_chain() as chain:
        chain.ainvoke.side_effect = Exception("Simulated LLM Timeout")

        state = {"messages": [HumanMessage(content="Who counters Darius?")]}
        result = await supervisor_node(state)

        assert [t["worker"] for t in result["plan"]] == ["GeneralAgent"]
        # A stale fanout=True from a previous turn would strand the lone worker
        # in an empty Synthesizer, so the fallback must reset it too.
        assert result["fanout"] is False
        assert isinstance(result["worker_results"], Overwrite)


@pytest.mark.asyncio
async def test_supervisor_resets_state_on_every_path():
    """Both channels are written even when the model returns a healthy plan."""
    with _stub_chain() as chain:
        chain.ainvoke.return_value = Plan(tasks=_plan(
            ("OPGGWorker", "win rate"), ("ResearchWorker", "sentiment"),
        ))

        result = await supervisor_node({"messages": [HumanMessage(content="hi")]})

        assert [t["worker"] for t in result["plan"]] == ["OPGGWorker", "ResearchWorker"]
        assert result["fanout"] is True
        assert isinstance(result["worker_results"], Overwrite)


@pytest.mark.asyncio
async def test_supervisor_handles_empty_plan():
    """An empty plan would produce no dispatch writes and halt the graph silently."""
    with _stub_chain() as chain:
        chain.ainvoke.return_value = Plan(tasks=[])

        result = await supervisor_node({"messages": [HumanMessage(content="hi")]})

        assert [t["worker"] for t in result["plan"]] == ["GeneralAgent"]
        assert result["fanout"] is False


# --- Plan normalization -----------------------------------------------------

def test_normalize_keeps_a_single_task():
    assert _normalize(_plan(("OPGGWorker", "a"))) == [{"worker": "OPGGWorker", "task": "a"}]


def test_normalize_dedupes_same_worker():
    """One worker can make several tool calls itself; two branches would collide."""
    out = _normalize(_plan(("OPGGWorker", "a"), ("OPGGWorker", "b")))
    assert [t["worker"] for t in out] == ["OPGGWorker"]
    assert out[0]["task"] == "a"


def test_normalize_keeps_a_valid_pair():
    out = _normalize(_plan(("OPGGWorker", "a"), ("ResearchWorker", "b")))
    assert [t["worker"] for t in out] == ["OPGGWorker", "ResearchWorker"]


def test_normalize_drops_general_agent_when_paired():
    """GeneralAgent has no tools, so pairing it just burns a branch."""
    out = _normalize(_plan(("GeneralAgent", "hi"), ("OPGGWorker", "a")))
    assert [t["worker"] for t in out] == ["OPGGWorker"]


def test_normalize_caps_fanout_width():
    out = _normalize(_plan(("OPGGWorker", "a"), ("ResearchWorker", "b"), ("GeneralAgent", "c")))
    assert len(out) == 2


def test_normalize_strips_task_whitespace():
    assert _normalize(_plan(("OPGGWorker", "  a  ")))[0]["task"] == "a"


# --- Worker return shape ----------------------------------------------------

def test_worker_return_fast_path_writes_messages():
    msgs = [AIMessage(content="answer", name="OPGGWorker")]
    assert worker_return({"fanout": False}, "OPGGWorker", msgs) == {"messages": msgs}


def test_worker_return_fanout_writes_only_results():
    """Under fan-out, tool transcripts must stay out of `messages`."""
    msgs = [
        AIMessage(content="", name="OPGGWorker", tool_calls=[
            {"name": "lol_get_champion_analysis", "args": {}, "id": "1"},
        ]),
        ToolMessage(content="huge json payload", name="lol_get_champion_analysis", tool_call_id="1"),
        AIMessage(content="Jinx is at 51.2%", name="OPGGWorker"),
    ]
    out = worker_return({"fanout": True, "task": "jinx win rate"}, "OPGGWorker", msgs)

    assert "messages" not in out
    assert out["worker_results"] == [{
        "worker": "OPGGWorker",
        "task": "jinx win rate",
        "answer": "Jinx is at 51.2%",
    }]


def test_worker_return_ignores_tool_call_messages_when_extracting_the_answer():
    msgs = [
        AIMessage(content="let me look", name="ResearchWorker", tool_calls=[
            {"name": "tavily_search", "args": {}, "id": "1"},
        ]),
        ToolMessage(content="results", name="tavily_search", tool_call_id="1"),
    ]
    out = worker_return({"fanout": True}, "ResearchWorker", msgs)
    # No final prose message, so there is no answer to report.
    assert out["worker_results"][0]["answer"] == ""


def test_worker_return_rejects_tool_call_markup_as_an_answer():
    """Regression: DeepSeek emitted <|DSML|tool_calls> as content on the final
    tool-free call, and that markup was reported as the worker's answer, so the
    stats it had already fetched were lost."""
    msgs = [
        AIMessage(content="Kayle is played Top: 51.0% win rate over 6,893 games.", name="OPGGWorker"),
        AIMessage(
            content='<|DSML|tool_calls>\n<|DSML|invoke name="lol_list_champion_details">',
            name="OPGGWorker",
        ),
    ]
    out = worker_return({"fanout": True, "task": "kayle win rate"}, "OPGGWorker", msgs)
    assert "51.0% win rate" in out["worker_results"][0]["answer"]


def test_worker_return_falls_back_to_empty_when_only_markup():
    msgs = [AIMessage(content="<tool_call>whatever</tool_call>", name="OPGGWorker")]
    out = worker_return({"fanout": True}, "OPGGWorker", msgs)
    assert out["worker_results"][0]["answer"] == ""


# --- History trimming -------------------------------------------------------

def test_recent_messages_trims_to_the_window():
    msgs = [HumanMessage(content=str(i)) for i in range(10)]
    assert [m.content for m in recent_messages(msgs, limit=3)] == ["7", "8", "9"]


def test_recent_messages_drops_orphaned_tool_results():
    """A slice starting on a ToolMessage is rejected by providers."""
    msgs = [
        AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "1"}]),
        ToolMessage(content="r", name="t", tool_call_id="1"),
        AIMessage(content="done"),
    ]
    out = recent_messages(msgs, limit=2)
    assert [type(m).__name__ for m in out] == ["AIMessage"]


def test_recent_messages_handles_empty():
    assert recent_messages([]) == []
    assert recent_messages(None) == []


# --- Sub-task prompt --------------------------------------------------------

def test_with_subtask_is_a_noop_without_a_task():
    assert with_subtask("BASE", None) == "BASE"
    assert with_subtask("BASE", "") == "BASE"


def test_with_subtask_appends_the_assignment():
    out = with_subtask("BASE", "get jinx win rate")
    assert out.startswith("BASE")
    assert "get jinx win rate" in out


# --- Retry wrapper ----------------------------------------------------------

@pytest.mark.asyncio
async def test_invoke_with_retry_succeeds_eventually():
    """Verify the tenacity retry logic works."""
    mock_agent = AsyncMock()
    # Fails twice, succeeds on third
    mock_agent.ainvoke.side_effect = [Exception("Fail 1"), Exception("Fail 2"), {"success": True}]

    result = await invoke_with_retry(mock_agent, [{"role": "user", "content": "hi"}])
    assert result == {"success": True}
    assert mock_agent.ainvoke.call_count == 3
