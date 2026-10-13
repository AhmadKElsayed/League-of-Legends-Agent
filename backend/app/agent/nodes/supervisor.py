import logging
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.types import Overwrite
from pydantic import BaseModel, Field
from typing import Literal
from app.agent_logger import log_node_transition
from app.agent.llm import get_llm, invoke_with_retry

logger = logging.getLogger("lol_agent")

llm = get_llm("deepseek/deepseek-v4-flash", temperature=0.1, max_tokens=1000)

# Only OPGGWorker + ResearchWorker can ever be paired, so a plan never needs
# more than two tasks.
MAX_TASKS = 2

WorkerName = Literal["GeneralAgent", "OPGGWorker", "ResearchWorker"]

class SubTask(BaseModel):
    worker: WorkerName
    task: str = Field(
        description="A self-contained restatement of the part of the user's request "
                    "this worker must answer. The worker does not see the other tasks."
    )

class Plan(BaseModel):
    tasks: list[SubTask] = Field(
        description="One task in almost every case. Two only when the user asked for "
                    "genuinely separate things owned by different specialists."
    )

system_prompt = """\
You are the routing supervisor for a League of Legends AI assistant team.
Your ONLY job is to read the conversation and decide which specialist(s) handle the user's request.

## YOUR TEAM
- **GeneralAgent** → Casual chat, greetings.
- **OPGGWorker** → Hard data from the OP.GG API: win rates, tier lists, builds and runes, \
player rank lookups, match history and match detail, lane matchup guides, champion synergies, \
esports schedules, pro player lookups.
- **ResearchWorker** → Subjective/community topics via web search: "Is X champion broken?", \
patch impact opinions, tier-list debates, Reddit/community sentiment, lore questions, \
champion abilities explained simply.

## HOW MANY TASKS
Emit **exactly one task** in almost every case. That one specialist answers the user directly.

Emit **two tasks** ONLY when the user asked for two genuinely different things that different
specialists own — typically hard numbers (OPGGWorker) *and* community opinion (ResearchWorker)
in the same message. When you do:
- Never emit two tasks for the same worker. One worker can make several tool calls itself.
- Never pair **GeneralAgent** with another worker.
- Write each `task` so it stands alone. The worker sees only its own task string plus the
  recent conversation, never the other task. Carry over any name, region, champion or role
  the user mentioned.

If one specialist can cover the whole request, use one task. Splitting costs time and money.

## ROUTING RULES (follow in order)
1. **Data vs Opinion**: raw stats, leaderboards, builds, profiles and match history → **OPGGWorker**. \
Opinions, community sentiment, lore, "is X broken" → **ResearchWorker**.
2. **Matchups & coaching**: what to pick into a matchup, what to build against a comp, or \
"analyze my recent games" → **OPGGWorker** (it owns the matchup, synergy and match-detail tools).
3. **Ambiguous requests**: when in doubt between OPGGWorker and ResearchWorker, prefer \
**OPGGWorker** (data is more reliable).

## EXAMPLES
- "hey whats up" → 1 task: GeneralAgent
- "what does yasuo's passive do?" → 1 task: ResearchWorker
- "tell me about jinx's lore" → 1 task: ResearchWorker
- "top 5 mid laners this patch" → 1 task: OPGGWorker
- "faker's rank in korea" → 1 task: OPGGWorker
- "best standard build for jinx adc" → 1 task: OPGGWorker
- "what should I pick against Syndra mid?" → 1 task: OPGGWorker
- "is darius op right now?" → 1 task: ResearchWorker
- "what's jinx's win rate this patch, and is the community saying she's broken?" → 2 tasks: \
OPGGWorker ("Get Jinx's current win rate and pick rate for ADC this patch") + \
ResearchWorker ("Find community sentiment on whether Jinx is overpowered this patch")
- "show me azir's build and explain why everyone hates playing him" → 2 tasks: \
OPGGWorker ("Get the standard build and runes for Azir mid") + \
ResearchWorker ("Find community opinion on why Azir is frustrating to play against")
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="messages"),
])

supervisor_chain = prompt | llm.with_structured_output(Plan)

_FALLBACK = [{"worker": "GeneralAgent", "task": ""}]

def _normalize(tasks) -> list[dict]:
    """Make the model's plan safe to dispatch: dedupe by worker, never pair
    GeneralAgent with a specialist, and cap the fan-out width."""
    seen = set()
    cleaned = []
    for t in tasks or []:
        if t.worker in seen:
            continue
        seen.add(t.worker)
        cleaned.append({"worker": t.worker, "task": (t.task or "").strip()})

    if len(cleaned) > 1:
        specialists = [t for t in cleaned if t["worker"] != "GeneralAgent"]
        if specialists:
            cleaned = specialists

    return cleaned[:MAX_TASKS]

async def supervisor_node(state):
    try:
        plan = await invoke_with_retry(supervisor_chain, {"messages": state["messages"]})
        tasks = _normalize(plan.tasks)
    except Exception:
        logger.exception("Supervisor failed to produce a plan; falling back to GeneralAgent")
        tasks = list(_FALLBACK)

    # An empty plan would produce no dispatch writes at all and the graph would
    # halt without answering.
    if not tasks:
        logger.warning("Supervisor returned an empty plan; falling back to GeneralAgent")
        tasks = list(_FALLBACK)

    log_node_transition("Supervisor", ", ".join(t["worker"] for t in tasks))

    # fanout and the worker_results reset must be written on EVERY return path:
    # both are persisted channels, and a stale value from a previous turn would
    # send a lone worker into an empty Synthesizer.
    return {
        "plan": tasks,
        "fanout": len(tasks) > 1,
        "worker_results": Overwrite([]),
    }
