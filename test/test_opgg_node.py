import asyncio
import os
from langchain_core.messages import HumanMessage
from app.agent.nodes.opgg_worker import opgg_worker_node

async def test_node_isolation():
    print("🚀 Testing OP.GG Worker Node in Isolation...")

    # 1. Setup Mock State (Thread A: Asking for Darius counters)
    # LangGraph nodes expect a dictionary (the state)
    mock_state = {
        "messages": [
            HumanMessage(content="Who counters Darius in RANKED TOP?")
        ]
    }

    try:
        # 2. Execute the node directly
        print("--- Executing Node ---")
        result = await opgg_worker_node(mock_state)

        # 3. Inspect the results
        # A node typically returns a dictionary that 'updates' the state
        new_messages = result.get("messages", [])
        
        print(f"\n✅ Node returned {len(new_messages)} new messages.")
        
        for i, msg in enumerate(new_messages):
            role = "AI" if i % 2 == 0 else "TOOL" # Simplification for debug
            print(f"\n[{role}]: {msg.content[:200]}...")
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                print(f"🛠️ Tool Call: {msg.tool_calls[0]['name']}")

    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Ensure your OLLAMA_BASE_URL is set for the local test
    if not os.getenv("OLLAMA_BASE_URL"):
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
        
    asyncio.run(test_node_isolation())