import pytest
from unittest.mock import patch, AsyncMock
from langchain_core.messages import HumanMessage
from app.agent.nodes.supervisor import supervisor_node
from app.agent.llm import invoke_with_retry

@pytest.mark.asyncio
async def test_supervisor_fallback_on_error():
    """Verify that if the LLM chain fails in the supervisor, it safely routes to the GeneralAgent."""
    with patch("app.agent.nodes.supervisor.supervisor_chain.ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.side_effect = Exception("Simulated LLM Timeout")
        
        state = {"messages": [HumanMessage(content="Who counters Darius?")]}
        result = await supervisor_node(state)
        
        assert result["next_node"] == "GeneralAgent"

@pytest.mark.asyncio
async def test_invoke_with_retry_succeeds_eventually():
    """Verify the tenacity retry logic works."""
    mock_agent = AsyncMock()
    # Fails twice, succeeds on third
    mock_agent.ainvoke.side_effect = [Exception("Fail 1"), Exception("Fail 2"), {"success": True}]
    
    result = await invoke_with_retry(mock_agent, [{"role": "user", "content": "hi"}])
    assert result == {"success": True}
    assert mock_agent.ainvoke.call_count == 3
