"""Interactive REPL against the real agent graph.

Run it directly (`uv run test/test_full_agent.py`) — it is a manual harness, not a
pytest test. It imports the real graph from app.agent.graph rather than rebuilding
one, so routing and fan-out behaviour here always match production.
"""
import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.agent.graph import workflow

load_dotenv()


async def main():
    print("🚀 Booting up League of Legends Agentic Graph...")

    # In-memory checkpointer so the REPL needs no Postgres.
    graph = workflow.compile(checkpointer=MemorySaver())

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

        print("\n🤖 Agentic Execution Log:")
        async for event in graph.astream(
            {"messages": [HumanMessage(content=user_input)]}, config, stream_mode="updates"
        ):
            for node_name, state_update in event.items():
                if node_name == "Supervisor":
                    plan = (state_update or {}).get("plan") or []
                    print(f"[Supervisor] dispatching -> {', '.join(t['worker'] for t in plan)}")
                else:
                    print(f"[{node_name}] finished task.")

        current_state = await graph.aget_state(config)
        final_message = current_state.values["messages"][-1]

        print("\n" + "=" * 50)
        print(f"🏆 COACH RESPONSE:\n{final_message.content}")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
