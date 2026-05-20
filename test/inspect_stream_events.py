from dotenv import load_dotenv
load_dotenv()

import asyncio
from langchain_core.messages import HumanMessage
from app.agent.graph import lol_agent

async def test_stream():
    config = {"configurable": {"thread_id": "test_inspect_stream"}}
    initial_state = {"messages": [HumanMessage(content="Hello! Who are you?")]}
    
    async for event in lol_agent.astream_events(initial_state, config, version="v2"):
        kind = event["event"]
        name = event["name"]
        metadata = event.get("metadata", {})
        node = metadata.get("langgraph_node")
        
        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            print(f"[{node}] ChatModelStream token: {repr(chunk.content)} | Metadata: {metadata}")
        elif kind == "on_chat_model_end":
            print(f"[{node}] ChatModelEnd")
        elif kind == "on_chain_start" and node:
            print(f"[{node}] ChainStart | Name: {name}")
        elif kind == "on_chain_end" and node:
            print(f"[{node}] ChainEnd | Name: {name}")

if __name__ == "__main__":
    asyncio.run(test_stream())
