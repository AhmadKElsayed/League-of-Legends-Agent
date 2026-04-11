import os
import pathlib
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from dotenv import load_dotenv

load_dotenv()

# llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
llm = ChatOllama(
    model="qwen2.5:72b", 
    temperature=0.2,
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
)

async def opgg_worker_node(state):
    # 1. Path logic
    possible_paths = [
        os.getenv("OPGG_MCP_PATH"),
        "./opgg-mcp/dist/index.js"
    ]
    opgg_server_path = next((p for p in possible_paths if p and pathlib.Path(p).exists()), None)
    
    if not opgg_server_path:
        raise FileNotFoundError("Could not find opgg-mcp entry point.")

    # 2. Supercharged Persona for Multi-Tool Use
    system_msg = SystemMessage(content="""You are the Ultimate League of Legends Analyst. 
        You have a massive suite of OPGG tools. Use the most specific tool for the task:

        --- TOOL CATEGORIES ---
        1. LIVE META & STATS:
        - 'lol_get_champion_analysis': Main tool for builds, runes, and counters.
        - 'lol_list_lane_meta_champions': Use to see who is currently 'Tier 1' or 'OP' in any lane.
        - 'lol_search_champion_meta': RAG search for deep mechanical knowledge or complex questions.
        - 'lol_list_items': Details on item build trees and costs.

        2. PLAYER & MATCH ANALYSIS:
        - 'lol_get_summoner_profile': Check rank, tier, and champion pool. (Needs Region!)
        - 'lol_list_summoner_matches': Review recent match history and performance.
        - 'lol_get_summoner_game_detail': Deep dive into a specific match's gold, bans, and builds.
        - 'lol_list_champion_leaderboard': See the top global players for a specific champion.

        3. STRATEGY & SYNERGY:
        - 'lol_get_lane_matchup_guide': Specific tips for 'My Champ vs Opponent Champ'.
        - 'lol_get_champion_synergies': Find which allies (e.g., Jungle/Support) pair best with a champion.
        - 'lol_list_champion_details': Lore, base stats, and enemy/ally gameplay tips.

        4. ESPORTS & NEWS:
        - 'lol_esports_list_schedules': Find upcoming pro matches (LCK, LPL, LEC, LCS).
        - 'lol_esports_list_team_standings': Check how pro teams are ranking in their leagues.
        - 'lol_get_pro_player_riot_id': Look up a pro's Riot ID (e.g., Faker) to find their profile.
        - 'lol_list_discounted_skins': Check current shop sales.

        5. SPECIAL MODES:
        - 'lol_list_aram_augments': Specialized stats for ARAM-specific buffs and performance.

        --- CRITICAL TECHNICAL RULES ---
        - REGION: If the user doesn't provide a region for a profile/match search, ASK them (e.g., KR, NA, EUW, EUNE).
        - DESIRED OUTPUT FIELDS: This is a CLOSED SET. You MUST read the tool description and only pick paths that exist (e.g., 'data.summary.average_stats.win_rate').
        - CASE SENSITIVITY: Use UPPER_SNAKE_CASE for champion names (e.g., 'LEE_SIN', 'DARIUS').
        """)

    node_name = "OP.GG hWorker"

    client = MultiServerMCPClient({
        "opgg": {
            "transport": "stdio",
            "command": "node",
            "args": [opgg_server_path]
        }
    })
    
    messages = [system_msg] + state["messages"]
    new_messages = []
    
    async with client.session("opgg") as session:
        # Load all tools and filter for LoL only
        all_tools = await load_mcp_tools(session)
        lol_tools = [t for t in all_tools if t.name.startswith("lol_")]
        
        tool_map = {tool.name: tool for tool in lol_tools}
        agent_with_tools = llm.bind_tools(lol_tools)
        
        # --- SELF-CORRECTION LOOP ---
        max_retries = 3
        attempts = 0
        
        while attempts < max_retries:
            response = await agent_with_tools.ainvoke(messages)
            
            # Tag the response so the Supervisor knows who spoke
            if isinstance(response, AIMessage):
                response.name = "OPGGWorker"
            
            new_messages.append(response)
            
            if not response.tool_calls:
                break
                
            messages.append(response)
            tool_execution_failed = False
            
            for tool_call in response.tool_calls:
                tool = tool_map[tool_call["name"]]
                try:
                    tool_result = await tool.ainvoke(tool_call["args"])
                    content = str(tool_result)
                except Exception as e:
                    content = f"API Error: {str(e)}. Please correct your arguments (especially desired_output_fields) and try again."
                    tool_execution_failed = True
                    print(f"⚠️ Tool '{tool_call['name']}' failed. Retrying... ({e})")
                
                tool_msg = ToolMessage(content=content, name=tool_call["name"], tool_call_id=tool_call["id"])
                messages.append(tool_msg)
                new_messages.append(tool_msg)
                
            if not tool_execution_failed:
                final_response = await agent_with_tools.ainvoke(messages)
                if isinstance(final_response, AIMessage):
                    final_response.name = node_name
                new_messages.append(final_response)
                break
                
            attempts += 1
            
            if attempts == max_retries:
                print("❌ Agent exhausted all search retries.")
            
    return {"messages": new_messages}