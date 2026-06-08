from dotenv import load_dotenv
load_dotenv()  # Must be first!

import os
import asyncio
from langchain_core.messages import HumanMessage
from app.agent.graph import lol_agent

async def test_stream():
    config = {"configurable": {"thread_id": "test_stream_session"}}
    initial_state = {"messages": [HumanMessage(content="Hello! Who are you?")]}
    
    print("Streaming events:")
    async for event in lol_agent.astream_events(initial_state, config, version="v2"):
        kind = event["event"]
        name = event["name"]
        print(f"Kind: {kind} | Name: {name}")
        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if chunk.content:
                print(f"  Token: {repr(chunk.content)}")

if __name__ == "__main__":
    asyncio.run(test_stream())
