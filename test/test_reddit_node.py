import asyncio
import os
from langchain_core.messages import HumanMessage
from app.agent.nodes.reddit_worker import reddit_worker_node

async def test_reddit_isolation():
    print("🚀 Testing Reddit Worker Node in Isolation...")

    # A typical prompt you'd send to the Reddit agent
    mock_state = {
        "messages": [
            HumanMessage(content="What is the Reddit community saying about the current state of Darius in the Top Lane? Are people complaining he is too strong?")
        ]
    }

    try:
        print("--- Executing Reddit Node ---")
        result = await reddit_worker_node(mock_state)

        new_messages = result.get("messages", [])
        
        print(f"\n✅ Node returned {len(new_messages)} new messages.")
        
        for i, msg in enumerate(new_messages):
            role = "AI" if i % 2 == 0 else "TOOL"
            # Print a snippet of the content so it doesn't flood the terminal
            snippet = msg.content[:300].replace('\n', ' ')
            print(f"\n[{role}]: {snippet}...")
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                print(f"🛠️ Tool Call: {msg.tool_calls[0]['name']}")

    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if not os.getenv("OLLAMA_BASE_URL"):
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
        
    asyncio.run(test_reddit_isolation())