from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from app.agent.state import AgentState
from app.agent.history import recent_messages
from app.agent.nodes.supervisor import supervisor_node
from app.agent.nodes.research_worker import research_worker_node
from app.agent.nodes.opgg_worker import opgg_worker_node
from app.agent.nodes.general import general_agent_node
from app.agent.nodes.synthesizer import synthesizer_node

WORKERS = ("GeneralAgent", "OPGGWorker", "ResearchWorker")

def create_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("Supervisor", supervisor_node)
    workflow.add_node("GeneralAgent", general_agent_node)
    workflow.add_node("OPGGWorker", opgg_worker_node)
    workflow.add_node("ResearchWorker", research_worker_node)
    # defer=True holds the Synthesizer back until no branch has work pending.
    workflow.add_node("Synthesizer", synthesizer_node, defer=True)

    # 1. Everything starts at the Supervisor
    workflow.add_edge(START, "Supervisor")

    # 2. Dispatch: one worker answers directly, or several run in parallel.
    def route_from_supervisor(state):
        tasks = state.get("plan") or [{"worker": "GeneralAgent", "task": ""}]

        # Fast path — a plain node name, routed through the path_map below, so
        # the worker streams its own tokens exactly as it always has.
        if len(tasks) == 1:
            return tasks[0]["worker"]

        # Fan-out. A Send payload REPLACES the node's input state, so it has to
        # carry `messages` itself; the worker would KeyError otherwise.
        return [
            Send(t["worker"], {
                "messages": recent_messages(state["messages"]),
                "task": t["task"],
                "fanout": True,
            })
            for t in tasks
        ]

    # Send objects bypass this map, but the fast path's plain string is looked
    # up in it — a missing worker name raises a bare KeyError.
    workflow.add_conditional_edges(
        "Supervisor",
        route_from_supervisor,
        {name: name for name in WORKERS},
    )

    # 3. A worker either answered the user (done) or fed the Synthesizer.
    def route_after_worker(state):
        return "Synthesizer" if state.get("fanout") else END

    for name in WORKERS:
        workflow.add_conditional_edges(
            name,
            route_after_worker,
            {"Synthesizer": "Synthesizer", END: END},
        )

    # No edge needed out of the Synthesizer: add_edge is a no-op when the
    # target is END.
    return workflow

workflow = create_graph()
lol_agent = workflow.compile()
