import os
import pathlib
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from dotenv import load_dotenv
from app.agent_logger import log_llm_response, log_tool_result
from app.agent.llm import get_llm, invoke_with_retry

load_dotenv()

# Global variables for persistent MCP session (configured via api.py lifespan)
mcp_session = None
mcp_client = None
mcp_tools = []

async def set_persistent_session(session, client, tools):
    global mcp_session, mcp_client, mcp_tools
    mcp_session = session
    mcp_client = client
    mcp_tools = tools

async def clear_persistent_session():
    global mcp_session, mcp_client, mcp_tools
    mcp_session = None
    mcp_client = None
    mcp_tools = []

llm = get_llm("deepseek/deepseek-v4-flash", temperature=0.2)

async def _execute_agent_loop(messages, lol_tools, tool_map, agent_with_tools, node_name):
    new_messages = []
    
    # --- SELF-CORRECTION & REASONING LOOP ---
    max_retries = 3
    attempts = 0
    
    while attempts < max_retries:
        try:
            response = await invoke_with_retry(agent_with_tools, messages)
        except Exception as e:
            print(f"❌ RecommendationWorker critical error: {e}")
            new_messages.append(AIMessage(content=f"An internal error occurred while communicating with the recommendation model: {e}", name="RecommendationWorker"))
            break
        
        # Tag the response so the Supervisor knows who spoke
        if isinstance(response, AIMessage):
            response.name = "RecommendationWorker"
        
        new_messages.append(response)
        log_llm_response(node_name, response)
        
        if not response.tool_calls:
            break
            
        messages.append(response)
        
        for tool_call in response.tool_calls:
            tool = tool_map[tool_call["name"]]
            try:
                tool_result = await tool.ainvoke(tool_call["args"])
                content = str(tool_result)
            except Exception as e:
                content = f"API Error: {str(e)}. Please check your arguments (especially desired_output_fields) and try again."
                print(f"⚠️ Tool '{tool_call['name']}' failed in RecommendationWorker. Retrying... ({e})")
            
            tool_msg = ToolMessage(content=content, name=tool_call["name"], tool_call_id=tool_call["id"])
            messages.append(tool_msg)
            new_messages.append(tool_msg)
            log_tool_result(node_name, tool_call["name"], tool_call["id"], content)
            
        # If this is the last attempt and we executed tool calls, do a final text synthesis
        if attempts + 1 == max_retries:
            try:
                final_response = await invoke_with_retry(llm, messages)
            except Exception as e:
                final_response = AIMessage(content=f"An internal error occurred in final recommendation synthesis: {e}", name="RecommendationWorker")
            if isinstance(final_response, AIMessage):
                final_response.name = node_name
            new_messages.append(final_response)
            log_llm_response(node_name, final_response)
            break
            
        attempts += 1
        
        if attempts == max_retries:
            print("❌ RecommendationWorker exhausted all tool retries.")
            
    return new_messages

async def recommendation_worker_node(state):
    # 1. Path logic for MCP fallback
    possible_paths = [
        os.getenv("OPGG_MCP_PATH"),
        "./opgg-mcp/dist/index.js",
        "../opgg-mcp/dist/index.js"
    ]
    opgg_server_path = next((p for p in possible_paths if p and pathlib.Path(p).exists()), None)
    
    if not opgg_server_path and mcp_session is None:
        return {"messages": [AIMessage(content="⚠️ RecommendationWorker Error: The OP.GG MCP server entry point was not found. Please verify `opgg-mcp/dist/index.js` is built.", name="RecommendationWorker")]}

    # 2. Expert Hextech AI Coach & Draft Strategist Persona
    system_msg = SystemMessage(content="""\
You are the **Hextech AI Coach & Draft Strategist (`RecommendationWorker`)**, an elite League of Legends tactical advisor and post-match playstyle analyst.
Your mission is to provide tailored, data-backed recommendations using your OP.GG MCP tools (`lol_get_champion_analysis`, `lol_get_champion_synergies`, `lol_get_lane_matchup_guide`, `lol_list_summoner_matches`, `lol_get_summoner_game_detail`, and `lol_get_summoner_profile`).

## TWO PRIMARY COACHING MODES

### MODE 1: DRAFT & SITUATIONAL ITEM ADVISOR (Option 1)
When the user asks for champion picks, counter matchups, synergies, or what situational items/runes to build against specific enemy compositions:
1. **Fetch Live Matchup Data**: Use `lol_get_champion_analysis` (for counter/win rate stats), `lol_get_lane_matchup_guide` (head-to-head tips), or `lol_get_champion_synergies` (ally pairings).
2. **Analyze Enemy Composition**: Identify primary damage types (% AD vs % AP), hard CC threats, dive potential, and tank/durability levels.
3. **Recommend Strategy**:
   - **Champion Picks**: Give 2-3 top recommendations with exact reasons (e.g., *"Pick Sylas because enemy mid/jungle have game-changing ultimates and low early MR"*).
   - **Situational Build Path**: Specify core items + exact situational counters (e.g., *"Rush Lord Dominik's Regards 3rd because enemy Sejuani+Orrn stack health armor"* or *"Build Maw of Malmortius against double AP burst"*).

### MODE 2: POST-MATCH PLAYSTYLE & PROFILE COACHING (Option 3)
When the user asks to analyze their recent match, review their OP.GG profile, or give playstyle recommendations based on played games:
1. **Verify Region**: If region is missing for summoner lookup, ask immediately (e.g., KR, NA, EUW, EUNE, OCE, etc.).
2. **Fetch Match & Profile Details**:
   - Call `lol_get_summoner_profile` to check overall rank and champion pool win rates.
   - Call `lol_list_summoner_matches` to inspect recent game outcomes and KDA trends.
   - Call `lol_get_summoner_game_detail` for specific matches to inspect individual player metrics: **items built over time, CS/min, wards/vision score, KDA, damage dealt vs taken, and gold curves**.
3. **Deliver a Actionable Coaching Report**:
   - **Performance Diagnostic**: Highlight what went right vs where the drop-off happened (e.g., *"Your CS/min in lane was strong (8.2), but vision score was only 9 in a 35-minute game."*).
   - **Build & Phase Critique**: Evaluate if their item path matched the enemy threats.
   - **Top 3 Actionable Takeaways**: Give exact, prioritized adjustments for their playstyle going into next games.

## CRITICAL TECHNICAL RULES
1. **DESIRED OUTPUT FIELDS**: Only request fields that exist in the tool schema (e.g., `data.summary.average_stats.win_rate` or `data.summoner.{game_name,tagline,level}`).
2. **CHAMPION NAMES**: Always use UPPER_SNAKE_CASE (e.g., `JINX`, `SYLAS`, `LEE_SIN`).
3. **POSITION VALUES**: Use exactly `"TOP"`, `"JUNGLE"`, `"MID"`, `"ADC"`, or `"SUPPORT"`.
4. **DATA FIRST**: Never make generic recommendations without backing them up with OP.GG data or tool calls when applicable.

## OUTPUT FORMATTING
- Format your response using rich, professional GitHub-style Markdown with clear section headers (`### 🎯 Draft & Counter Strategy` or `### 📊 Post-Match Coaching Analysis`).
- Use bullet points, bold key stats (win rates, CS numbers, vision scores), and clear callouts.
- Conclude every response with an **Authoritative Hextech Takeaway** to inspire improvement!
""")

    node_name = "RecommendationWorker"
    messages = [system_msg] + state["messages"]

    if mcp_session is not None:
        tool_map = {tool.name: tool for tool in mcp_tools}
        agent_with_tools = llm.bind_tools(mcp_tools)
        new_messages = await _execute_agent_loop(messages, mcp_tools, tool_map, agent_with_tools, node_name)
    else:
        client = MultiServerMCPClient({
            "opgg": {
                "transport": "stdio",
                "command": "node",
                "args": [opgg_server_path]
            }
        })
        async with client.session("opgg") as session:
            all_tools = await load_mcp_tools(session)
            lol_tools = [t for t in all_tools if t.name.startswith("lol_") or t.name.startswith("tft_")]
            tool_map = {tool.name: tool for tool in lol_tools}
            agent_with_tools = llm.bind_tools(lol_tools)
            new_messages = await _execute_agent_loop(messages, lol_tools, tool_map, agent_with_tools, node_name)
            
    return {"messages": new_messages}
