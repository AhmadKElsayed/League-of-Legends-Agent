import os
import uuid
import asyncio
from dotenv import load_dotenv

# 1. Load Environment Variables First!
load_dotenv()

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
import operator
from typing import TypedDict, Annotated, Sequence

# 2. Import your hard work!
from app.agent.nodes.opgg_worker import opgg_worker_node
from app.agent.nodes.reddit_worker import reddit_worker_node
from app.agent.nodes.supervisor import supervisor_node

# --- GRAPH STATE DEFINITION ---
# This tells LangGraph what data is being passed between nodes
class AgentState(TypedDict):
    # 'operator.add' ensures new messages are appended to the list, not overwritten
    messages: Annotated[Sequence, operator.add]
    next_node: str

# --- THE GENERAL AGENT NODE ---
# A simple LLM call for casual chat when OP.GG or Reddit aren't needed
llm = ChatOllama(
    model="llama3.1", 
    temperature=0.7, # A bit more creative for casual chat
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
)

async def general_agent_node(state):
    print("--- 💬 General Agent Thinking ---")
    response = await llm.ainvoke(state["messages"])
    return {"messages": [response]}

# --- BUILD THE GRAPH ---
async def main():
    print("🚀 Booting up League of Legends Agentic Graph...")
    
    builder = StateGraph(AgentState)

    # Add all your nodes
    builder.add_node("Supervisor", supervisor_node)
    builder.add_node("GeneralAgent", general_agent_node)
    builder.add_node("OPGGWorker", opgg_worker_node)
    builder.add_node("RedditWorker", reddit_worker_node)

    # 1. Everything starts at the Supervisor
    builder.add_edge(START, "Supervisor")

    # 2. Conditional Routing Logic
    def route_from_supervisor(state):
        # The supervisor node returned a dict with 'next_node'
        return state["next_node"]

    builder.add_conditional_edges(
        "Supervisor",
        route_from_supervisor,
        {
            "GeneralAgent": "GeneralAgent",
            "OPGGWorker": "OPGGWorker",
            "RedditWorker": "RedditWorker",
            "FINISH": END
        }
    )

    # 3. After a worker finishes, it must report back to the Supervisor
    builder.add_edge("GeneralAgent", END)
    builder.add_edge("OPGGWorker", END)
    builder.add_edge("RedditWorker", END)

    # 4. Add Memory (Checkpointer) so it remembers your lane!
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)

    # --- INTERACTIVE CHAT LOOP ---
    # We assign a static thread ID so the memory persists for this session
    config = {"configurable": {"thread_id": "blackwell_session_1"}}
    
    print("\n✅ Agent Online! Type 'exit' or 'quit' to stop.")
    print("-" * 50)

    while True:
        user_input = input("\n🧑 User: ")
        
        if user_input.lower() in ["exit", "quit", "q"]:
            print("Shutting down Agent...")
            break
            
        if not user_input.strip():
            continue

        # Stream the graph execution
        print("\n🤖 Agentic Execution Log:")
        async for event in graph.astream({"messages": [HumanMessage(content=user_input)]}, config, stream_mode="updates"):
            # This loop just prints out which node just fired
            for node_name, state_update in event.items():
                if node_name == "Supervisor":
                    continue # Supervisor already prints its routing decision
                print(f"[{node_name}] finished task.")
        
        # After the graph finishes, fetch the final message from the state
        current_state = graph.get_state(config)
        final_message = current_state.values["messages"][-1]
        
        print("\n" + "="*50)
        print(f"🏆 COACH RESPONSE:\n{final_message.content}")
        print("="*50)

if __name__ == "__main__":
    asyncio.run(main())