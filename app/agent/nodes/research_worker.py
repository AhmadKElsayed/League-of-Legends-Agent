import os
from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from langchain_tavily import TavilySearch

load_dotenv()

llm = ChatOpenRouter(model="deepseek/deepseek-v4-flash", temperature=0.5)
# llm = ChatOllama(
#     model="qwen2.5:72b", 
#     temperature=0,
#     base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# )

tavily_tool = TavilySearch(max_results=5)

async def research_worker_node(state):
    system_msg = SystemMessage(content="""\
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

## REPORT STRUCTURE
Your final response MUST follow this format:

### Current Meta Status
_Where does this champion/topic stand in the current meta? Include any relevant win rate or pick rate context._

### Community Sentiment
_What are players saying? Quote or paraphrase specific Reddit threads, pro opinions, or community debates. Mention if sentiment is divided._

### The Verdict
_Your clear, opinionated recommendation. Don't sit on the fence — give the user a direct answer with reasoning._

### Sources
_List 2-3 of the most relevant sources with brief descriptions of what they contain._

## TONE & STYLE
- Be conversational but authoritative — like an analyst on a League podcast.
- Take a clear stance on controversial topics, but acknowledge the other side.
- Use **bold** for emphasis and key data points.
- Keep the total response to ~300 words — dense and valuable, not padded.
- Never say "based on my research" — just present the findings confidently.
""")

    messages = [system_msg] + state["messages"]
    
    # Identify the node for the Supervisor
    node_name = "ResearchWorker"
    
    # 2. THE ADVANCED REASONING LOOP
    max_retries = 3
    attempts = 0
    new_messages = []

    agent_with_tools = llm.bind_tools([tavily_tool])

    while attempts < max_retries:
        # Acknowledge the thinking process
        response = await agent_with_tools.ainvoke(messages)
        
        # Tag the AIMessage immediately
        if isinstance(response, AIMessage):
            response.name = node_name
            
        new_messages.append(response)

        if not response.tool_calls:
            break

        messages.append(response)
        
        # Parallel Execution handling (if the LLM generates multiple tool calls at once)
        tool_results_found = False
        for tool_call in response.tool_calls:
            try:
                # Execution
                result = await tavily_tool.ainvoke(tool_call["args"])
                content = str(result)

                if content == "[]" or not content:
                    content = f"The query '{tool_call['args'].get('query')}' yielded no results. Please try a more specific LoL-related query."
                else:
                    tool_results_found = True

            except Exception as e:
                content = f"Search Error: {str(e)}. Attempting to recover..."
            
            t_msg = ToolMessage(content=content, name=tool_call["name"], tool_call_id=tool_call["id"])
            messages.append(t_msg)
            new_messages.append(t_msg)

        # If we got valid data, do a final synthesis
        if tool_results_found:
            final_report = await agent_with_tools.ainvoke(messages)
            if isinstance(final_report, AIMessage):
                final_report.name = node_name
            new_messages.append(final_report)
            break
            
        attempts += 1
        print(f"🔄 {node_name} is pivoting search strategy (Attempt {attempts}/{max_retries})")

    return {"messages": new_messages}