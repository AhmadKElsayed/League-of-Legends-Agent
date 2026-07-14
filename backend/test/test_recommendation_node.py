import asyncio
import os
from langchain_core.messages import HumanMessage
from app.agent.nodes.recommendation_worker import recommendation_worker_node
from app.agent.nodes.supervisor import supervisor_node

async def test_recommendation_node():
    print("🚀 Testing RecommendationWorker Node & Routing...")

    # 1. Test Supervisor Routing to RecommendationWorker
    print("\n--- Test 1: Supervisor Routing ---")
    mock_draft_state = {
        "messages": [
            HumanMessage(content="What should I pick against Zed mid and what situational items do I build?")
        ]
    }
    route_result = await supervisor_node(mock_draft_state)
    print(f"Routing Decision for Draft/Build query: {route_result['next_node']}")
    assert route_result["next_node"] == "RecommendationWorker", f"Expected RecommendationWorker, got {route_result['next_node']}"

    mock_coaching_state = {
        "messages": [
            HumanMessage(content="Check Hide on bush profile on KR and analyze his last match to give me a playstyle coaching breakdown of what made the difference.")
        ]
    }
    route_result_2 = await supervisor_node(mock_coaching_state)
    print(f"Routing Decision for Coaching query: {route_result_2['next_node']}")
    assert route_result_2["next_node"] == "RecommendationWorker", f"Expected RecommendationWorker, got {route_result_2['next_node']}"

    # 2. Test RecommendationWorker execution in isolation
    print("\n--- Test 2: RecommendationWorker Node Execution ---")
    try:
        result = await recommendation_worker_node(mock_draft_state)
        new_messages = result.get("messages", [])
        print(f"✅ RecommendationWorker returned {len(new_messages)} messages.")
        for i, msg in enumerate(new_messages):
            role = getattr(msg, "name", "AI/TOOL")
            print(f"[{role}]: {str(msg.content)[:250]}...")
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                print(f"🛠️ Tool Call: {msg.tool_calls[0]['name']} (args: {msg.tool_calls[0]['args']})")
    except Exception as e:
        print(f"❌ RecommendationWorker execution error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_recommendation_node())
