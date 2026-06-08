import os
import asyncio
import pathlib
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

async def inspect_tools():
    possible_paths = [
        os.getenv("OPGG_MCP_PATH"),
        "./opgg-mcp/dist/index.js"
    ]
    opgg_server_path = next((p for p in possible_paths if p and pathlib.Path(p).exists()), None)
    
    if not opgg_server_path:
        print("❌ Could not find opgg-mcp path.")
        return

    client = MultiServerMCPClient({
        "opgg": {
            "transport": "stdio",
            "command": "node",
            "args": [opgg_server_path]
        }
    })
    
    async with client.session("opgg") as session:
        opgg_tools = await load_mcp_tools(session)
        lol_tools = [t for t in opgg_tools if t.name.startswith("lol_")]
        print(f"Total LoL tools: {len(lol_tools)}")
        for t in lol_tools:
            print(f"- {t.name}: {t.description}")

if __name__ == "__main__":
    asyncio.run(inspect_tools())
