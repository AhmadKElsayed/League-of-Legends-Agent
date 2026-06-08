import os
import asyncio
import pathlib
import json
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
        print(f"\n🔍 Found {len(opgg_tools)} tool(s)!")
        
        for tool in opgg_tools:
            print("\n" + "="*50)
            print(f"🛠️ Tool Name: {tool.name}")
            print(f"📝 Description: {tool.description}")
            
            print("📦 Arguments:")
            try:
                # Check if it's a Pydantic model
                if hasattr(tool.args_schema, "model_json_schema"):
                    schema = tool.args_schema.model_json_schema()
                # If it's already a dict, just use it
                elif isinstance(tool.args_schema, dict):
                    schema = tool.args_schema
                else:
                    schema = str(tool.args_schema)
                
                print(json.dumps(schema, indent=2))
            except Exception as e:
                print(f"Could not parse schema: {e}")
            print("="*50)

if __name__ == "__main__":
    asyncio.run(inspect_tools())