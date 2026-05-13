import os
from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from langchain_tavily import TavilySearch

load_dotenv()

llm = ChatOpenRouter(model="deepseek/deepseek-v4-flash", temperature=0.4)
# llm = ChatOllama(
#     model="qwen2.5:72b", 
#     temperature=0,
#     base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# )

tavily_tool = TavilySearch(max_results=5)

async def research_worker_node(state):
    system_msg = SystemMessage(content="""You are an Elite LoL Research Lead. 
    Your goal is to provide a 'Community Pulse' report.
    
    STRATEGY:
    1. BREAKDOWN: Split complex requests into multiple search queries (e.g. 'Darius winrate' AND 'Darius reddit complaints').
    2. SOURCE VERIFICATION: Prioritize results from Reddit, Patch Notes, and Pro-analysis sites.
    3. STRUCTURE: Your final summary MUST include:
       - [Current Meta Status]
       - [Community Sentiment/Reddit Trends]
       - [Actionable Advice for the User]
    
    If the search returns '[]', you have failed. You MUST adjust keywords and try again.""")

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