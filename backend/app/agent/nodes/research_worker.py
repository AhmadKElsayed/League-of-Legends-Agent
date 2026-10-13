import os
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage, HumanMessage
from langchain_tavily import TavilySearch
from app.agent_logger import log_llm_response, log_tool_result
from app.agent.llm import get_llm, invoke_with_retry
from app.agent.prompts import with_subtask, FINAL_SYNTHESIS_INSTRUCTION, RESEARCH_OUTPUT_FORMAT
from app.agent.state import worker_return

load_dotenv()

llm = get_llm("deepseek/deepseek-v4-flash", temperature=0.3)

tavily_tool = TavilySearch(max_results=5)

async def research_worker_node(state):
    system_msg = SystemMessage(content=with_subtask("""\
You are the **LoL Research Analyst**, an elite investigator who synthesizes community sentiment, patch analysis, and strategic insights into actionable intelligence reports.

## YOUR MISSION
Deliver a **Community Intelligence Report** that gives the user a clear, opinionated answer backed by real sources.

## SEARCH STRATEGY
1. **Multi-query approach**: Always run at least 2 searches to triangulate information:
   - One factual query (e.g., "champion name win rate patch 14.x")
   - One sentiment query (e.g., "champion name reddit opinion nerf buff")
2. **Source priority** (most to least reliable):
   - Official Riot patch notes and dev blogs
   - Reddit r/leagueoflegends and champion-specific subreddits
   - Pro player streams/interviews (via articles)
   - Tier list sites (u.gg, op.gg, mobalytics)
   - General gaming news outlets
3. **If a search returns empty** (`[]`), immediately reformulate with different keywords. Try:
   - Removing filler words
   - Using champion nicknames or abbreviations
   - Adding "2026" or current season number

""" + RESEARCH_OUTPUT_FORMAT, state.get("task")))

    messages = [system_msg] + list(state["messages"])
    
    # Identify the node for the Supervisor
    node_name = "ResearchWorker"
    
    # 2. THE ADVANCED REASONING LOOP
    max_retries = 5
    attempts = 0
    new_messages = []

    agent_with_tools = llm.bind_tools([tavily_tool])

    while attempts < max_retries:
        try:
            # Last attempt: unbind tools AND say so, otherwise the model emits a
            # tool call as raw markup in the content (see FINAL_SYNTHESIS_INSTRUCTION).
            if attempts == max_retries - 1:
                response = await invoke_with_retry(
                    llm, messages + [HumanMessage(content=FINAL_SYNTHESIS_INSTRUCTION)]
                )
            else:
                response = await invoke_with_retry(agent_with_tools, messages)
        except Exception as e:
            print(f"❌ ResearchWorker critical error: {e}")
            new_messages.append(AIMessage(content=f"An internal error occurred while researching: {e}", name="ResearchWorker"))
            break
        
        # Tag the AIMessage immediately
        if isinstance(response, AIMessage):
            response.name = node_name
            
        new_messages.append(response)
        log_llm_response(node_name, response)

        if not response.tool_calls:
            break

        messages.append(response)
        
        # Execute tool calls
        for tool_call in response.tool_calls:
            try:
                # Execution
                result = await tavily_tool.ainvoke(tool_call["args"])
                content = str(result)

                if content == "[]" or not content:
                    content = f"The query '{tool_call['args'].get('query')}' yielded no results. Please try a more specific LoL-related query."

            except Exception as e:
                content = f"Search Error: {str(e)}. Attempting to recover..."
            
            t_msg = ToolMessage(content=content, name=tool_call["name"], tool_call_id=tool_call["id"])
            messages.append(t_msg)
            new_messages.append(t_msg)
            log_tool_result(node_name, tool_call["name"], tool_call["id"], content)

        attempts += 1
        print(f"🔄 {node_name} completed step {attempts}/{max_retries}")

    return worker_return(state, "ResearchWorker", new_messages)