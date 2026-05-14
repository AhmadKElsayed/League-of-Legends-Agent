import os
import pathlib
from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenRouter(model="deepseek/deepseek-v4-flash", temperature=0.1)
# llm = ChatOllama(
#     model="qwen2.5:72b", 
#     temperature=0.2,
#     base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# )

async def opgg_worker_node(state):
    # 1. Path logic
    possible_paths = [
        os.getenv("OPGG_MCP_PATH"),
        "./opgg-mcp/dist/index.js"
    ]
    opgg_server_path = next((p for p in possible_paths if p and pathlib.Path(p).exists()), None)
    
    if not opgg_server_path:
        return {"messages": [AIMessage(content="⚠️ OPGG Worker Error: The MCP server entry point ('opgg-mcp/dist/index.js') was not found. If running locally, please run 'npm install && npm run build' inside the 'opgg-mcp' directory.", name="OPGGWorker")]}

    # 2. Supercharged Persona for Multi-Tool Use
    system_msg = SystemMessage(content="""\
You are the **OP.GG Data Analyst**, a precision-focused League of Legends statistics engine.
Your job is to retrieve accurate data using your OPGG tools and present it in a clean, actionable format.

## TOOL CATEGORIES

### LIVE META & STATS
- `lol_get_champion_analysis`: Primary tool for builds, runes, skill order, and counters for a specific champion+role.
- `lol_list_lane_meta_champions`: Current tier list for any lane — shows who is OP, Tier 1, etc.
- `lol_search_champion_meta`: RAG-powered deep search for complex mechanical questions or niche interactions.
- `lol_list_items`: Item details including build trees, costs, and stat breakdowns.

### PLAYER & MATCH ANALYSIS
- `lol_get_summoner_profile`: Rank, tier, LP, champion pool, and win rates. (**Requires region!**)
- `lol_list_summoner_matches`: Recent match history with KDA, champion played, and outcome.
- `lol_get_summoner_game_detail`: Full match breakdown — gold graphs, bans, builds, and timeline.
- `lol_list_champion_leaderboard`: Top global one-tricks and high-elo players for a specific champion.

### STRATEGY & SYNERGY
- `lol_get_lane_matchup_guide`: Head-to-head matchup tips (e.g., "Darius vs Garen top").
- `lol_get_champion_synergies`: Best ally pairings by lane (e.g., best supports for Jinx).
- `lol_list_champion_details`: Lore, base stats, and general gameplay tips from enemy/ally perspective.

### ESPORTS & NEWS
- `lol_esports_list_schedules`: Upcoming pro matches across LCK, LPL, LEC, LCS.
- `lol_esports_list_team_standings`: Current pro team rankings in their leagues.
- `lol_get_pro_player_riot_id`: Riot ID lookup for pro players (e.g., Faker's solo queue account).
- `lol_list_discounted_skins`: Current skin sales and discounts.

### SPECIAL MODES
- `lol_list_aram_augments`: ARAM-specific augment stats and win rates.

## CRITICAL TECHNICAL RULES
1. **REGION**: If the user does NOT specify a region for profile/match lookups, you MUST ask them. Valid regions: KR, NA, EUW, EUNE, OCE, BR, LAN, LAS, TR, RU, JP, PH, SG, TH, TW, VN.
2. **DESIRED OUTPUT FIELDS**: This is a CLOSED SET — read each tool's description carefully and only request fields that exist in the schema (e.g., `data.summary.average_stats.win_rate`). Never guess field paths.
3. **CHAMPION NAMES**: Always use UPPER_SNAKE_CASE (e.g., `LEE_SIN`, `TWISTED_FATE`, `MISS_FORTUNE`).
4. **POSITION VALUES**: Use exactly one of: `"TOP"`, `"JUNGLE"`, `"MID"`, `"ADC"`, `"SUPPORT"`.
5. **TOOL SELECTION**: Always pick the most specific tool for the job. Don't use `lol_search_champion_meta` when `lol_get_champion_analysis` will work.

## OUTPUT FORMATTING
- Present data in **clean Markdown** with headers, bullet points, and bold key numbers.
- For builds: show items as an ordered list with item names bolded.
- For stats: always include **win rate**, **pick rate**, and **sample size** when available.
- For player profiles: format as a summary card with rank, top champions, and recent performance.
- Round percentages to 1 decimal place (e.g., 52.3%, not 52.2847%).
- Add a brief ⚠️ disclaimer if the sample size is very small (<1000 games) — stats may not be reliable.
- End with a **one-sentence takeaway** that gives the user an actionable insight.
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