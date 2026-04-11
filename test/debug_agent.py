import asyncio
import os
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

# 1. Setup LLM (Pointing to your local Ollama)
llm = ChatOllama(
    model="llama3.1",
    temperature=0,
    base_url="http://localhost:11434"
)

async def run_debug():
    print("--- Starting Local Debug ---")
    
    # 2. Define the exact path to your compiled MCP server
    # Use an absolute path to be safe
    mcp_path = os.path.expanduser("~/LOL-Agent/opgg-mcp/dist/index.js")
    
    if not os.path.exists(mcp_path):
        print(f"ERROR: Could not find {mcp_path}")
        return

    # 3. Initialize MCP Client
    client = MultiServerMCPClient({
        "opgg": {
            "transport": "stdio",
            "command": "node",
            "args": [mcp_path]
        }
    })

    # 4. Mock the Worker Logic
    system_msg = SystemMessage(content="""You are a professional League of Legends coach.
    When using 'lol_get_champion_analysis', you MUST use these exact values:
    - game_mode: Must be one of ['RANKED', 'FLEX', 'URF', 'ARAM', 'NEXUS_BLITZ']
    - position: Must be one of ['TOP', 'JUNGLE', 'MID', 'ADC', 'SUPPORT']

    Default to 'RANKED' and 'TOP' if the user doesn't specify.""")
    user_msg = HumanMessage(content="Who counters Darius in Ranked Solo Top lane?")
    
    print("--- Connecting to MCP Server ---")
    try:
        async with client.session("opgg") as session:
                from langchain_mcp_adapters.tools import load_mcp_tools
                from langchain_core.messages import ToolMessage
                
                print("--- Loading Tools ---")
                tools = await load_mcp_tools(session)
                tool_map = {tool.name: tool for tool in tools}
                agent = llm.bind_tools(tools)
                
                # 1. First Pass: LLM decides to use a tool
                messages = [system_msg, user_msg]
                response = await agent.ainvoke(messages)
                messages.append(response)
                
                if response.tool_calls:
                    print(f"--- Executing Tool: {response.tool_calls[0]['name']} ---")
                    
                    for tool_call in response.tool_calls:
                        # 2. Run the actual OP.GG Tool
                        tool = tool_map[tool_call["name"]]
                        tool_result = await tool.ainvoke(tool_call["args"])
                        
                        # 3. Add the result to the conversation
                        messages.append(ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_call["id"]
                        ))
                    
                    # 4. Final Pass: LLM summarizes the data
                    print("--- Final Summarization (Blackwell Speed) ---")
                    final_response = await agent.ainvoke(messages)
                    print("\nCOACH ADVICE:")
                    print(final_response.content)
            
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_debug())