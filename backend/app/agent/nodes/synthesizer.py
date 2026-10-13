import logging
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.agent_logger import log_llm_response
from app.agent.llm import get_llm, invoke_with_retry
from app.agent.history import recent_messages
from app.agent.prompts import WORKER_OUTPUT_FORMATS

logger = logging.getLogger("lol_agent")

llm = get_llm("deepseek/deepseek-v4-flash", temperature=0.3)

# Friendly labels so the model never sees (and never echoes) internal node names.
SOURCE_LABELS = {
    "OPGGWorker": "OP.GG statistics",
    "ResearchWorker": "Community research",
    "GeneralAgent": "General knowledge",
}

_HEADER = """\
You are **Nexus**, a charismatic League of Legends companion.

The user asked a question with several parts, and each part has already been answered by a
specialist. Your job is to deliver those answers as ONE reply — **assembled, not rewritten**.

## THE ONE RULE THAT MATTERS
A compound answer must look exactly like the single answers the user is used to. Each part of
the reply keeps the **full section structure and formatting of its own contract below** — all
headings, all required fields, all required closing lines. You are stitching finished sections
together, not summarizing them into your own prose.

That means:
- **Never drop a required section.** If a contract asks for `### Sources`, the reply has it.
- **Never drop a required field.** Win rate, pick rate, sample size, the ⚠️ small-sample
  disclaimer, 1-decimal rounding — if the contract asks for it and the data has it, it stays.
- **Never flatten a table or list into a paragraph.**
- Preserve each section's own wording and detail. Trim only genuine repetition between parts,
  and fix the seams so it reads as one reply rather than two documents bolted together.
"""

_FOOTER = """\
## ASSEMBLY
- Order the parts the way the user asked for them.
- Put each part under its own `###` heading, in the specialist's own structure.
- Where two parts overlap, say it once, in the part where it belongs best.
- When two parts disagree on a number, trust the **OP.GG statistics** and note plainly that the
  community's read differs from what the data shows.
- Never invent statistics. Only use numbers that appear in the findings.
- If a part came back empty or errored, say so in one short line and keep the rest intact. Never
  claim data is missing when a value for it appears in the findings.
- Never mention "findings", "sources", "specialists", "workers", or how the reply was assembled.
- At most one short closing line tying the parts together. Each section keeps its own ending.
"""


def _system_prompt(workers) -> str:
    """Header + the output contract of each specialist that actually ran + assembly rules."""
    contracts = []
    for worker in dict.fromkeys(workers):          # de-duped, order preserved
        contract = WORKER_OUTPUT_FORMATS.get(worker)
        if contract:
            label = SOURCE_LABELS.get(worker, worker)
            contracts.append(f"# CONTRACT — the {label} part MUST follow this exactly\n\n{contract}")
    return "\n\n".join([_HEADER, *contracts, _FOOTER])


async def synthesizer_node(state):
    results = state.get("worker_results") or []

    # Defensive: a stale fanout flag could route a lone worker here with nothing
    # to merge. Better a short honest reply than an empty bubble.
    if not results:
        logger.warning("Synthesizer reached with no worker results; returning a fallback reply.")
        return {"messages": [AIMessage(
            content="I wasn't able to gather that one. Could you rephrase it for me?",
            name="Synthesizer",
        )]}

    findings = "\n\n".join(
        f"### {SOURCE_LABELS.get(r.get('worker'), r.get('worker', 'Unknown'))}"
        + (f" — {r['task']}" if r.get("task") else "")
        + f"\n{r.get('answer') or '(no result returned)'}"
        for r in results
    )

    messages = [
        SystemMessage(content=_system_prompt([r.get("worker") for r in results])),
        *recent_messages(state["messages"]),
        HumanMessage(content=f"Findings gathered for the question above:\n\n{findings}"),
    ]

    try:
        response = await invoke_with_retry(llm, messages)
    except Exception as e:
        logger.exception("Synthesizer failed to merge worker results")
        return {"messages": [AIMessage(
            content=f"An internal error occurred while putting that answer together: {e}",
            name="Synthesizer",
        )]}

    if isinstance(response, AIMessage):
        response.name = "Synthesizer"
    log_llm_response("Synthesizer", response)
    return {"messages": [response]}
