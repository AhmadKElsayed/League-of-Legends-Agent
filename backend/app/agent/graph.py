from langgraph.graph import StateGraph, START, END
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from app.agent.state import AgentState
from app.agent.nodes.supervisor import supervisor_node
from app.agent.nodes.research_worker import research_worker_node
from app.agent.nodes.opgg_worker import opgg_worker_node
from app.agent.nodes.general import general_agent_node

def create_graph():
    workflow = StateGraph(AgentState)

    # Add all your nodes
    workflow.add_node("Supervisor", supervisor_node)
    workflow.add_node("GeneralAgent", general_agent_node)
    workflow.add_node("OPGGWorker", opgg_worker_node)
    workflow.add_node("ResearchWorker", research_worker_node)

    # 1. Everything starts at the Supervisor
    workflow.add_edge(START, "Supervisor")

    # 2. Conditional Routing Logic
    def route_from_supervisor(state):
        # The supervisor node returned a dict with 'next_node'
        return state["next_node"]

    workflow.add_conditional_edges(
        "Supervisor",
        route_from_supervisor,
        {
            "GeneralAgent": "GeneralAgent",
            "OPGGWorker": "OPGGWorker",
            "ResearchWorker": "ResearchWorker",
            "FINISH": END
        }
    )

    workflow.add_edge("GeneralAgent", END)
    workflow.add_edge("OPGGWorker", END)
    workflow.add_edge("ResearchWorker", END)
    return workflow

workflow = create_graph()
lol_agent = workflow.compile()