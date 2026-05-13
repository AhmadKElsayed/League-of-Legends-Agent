import os
import uuid
import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openrouter import ChatOpenRouter
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
import operator
from typing import TypedDict, Annotated, Sequence
from app.agent.nodes.opgg_worker import opgg_worker_node
from app.agent.nodes.research_worker import research_worker_node
from app.agent.nodes.supervisor import supervisor_node

load_dotenv()

# --- GRAPH STATE DEFINITION ---
class AgentState(TypedDict):
    messages: Annotated[Sequence, operator.add]
    next_node: str

# --- THE GENERAL AGENT NODE ---
llm = ChatOpenRouter(
    model="google/gemini-2.5-flash-lite", 
    temperature=0.7
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
    builder.add_node("ResearchWorker", research_worker_node)

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
            "ResearchWorker": "ResearchWorker",
            "FINISH": END
        }
    )

    # 3. After a worker finishes, it must report back to the Supervisor
    builder.add_edge("GeneralAgent", END)
    builder.add_edge("OPGGWorker", END)
    builder.add_edge("ResearchWorker", END)

    # 4. Add Memory (Checkpointer) so it remembers your lane!
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)

    # --- INTERACTIVE CHAT LOOP ---
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