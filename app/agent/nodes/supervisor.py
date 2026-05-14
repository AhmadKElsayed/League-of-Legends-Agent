import os
from langchain_openrouter import ChatOpenRouter
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel
from typing import Literal

llm = ChatOpenRouter(model="deepseek/deepseek-v4-flash", temperature=0.0)

class Router(BaseModel):
    next_node: Literal["FINISH", "GeneralAgent", "OPGGWorker", "ResearchWorker"]

system_prompt = """\
You are the routing supervisor for a League of Legends AI assistant team.
Your ONLY job is to read the conversation and decide which specialist handles the NEXT step.

## YOUR TEAM
- **GeneralAgent** → Casual chat, greetings.
- **OPGGWorker** → Hard data requests: win rates, tier lists, optimal builds/runes, player profiles, match history, ranked stats, champion counters, item analysis, esports schedules, pro player lookups.
- **ResearchWorker** → Subjective/community topics: "Is X champion broken?", niche matchup advice, patch impact opinions, tier-list debates, Reddit/community sentiment, strategy guides not covered by raw stats, lore questions, champion abilities explained simply.

## ROUTING RULES (follow in order)
1. **FINISH first**: If the LAST message in the conversation is from a worker (GeneralAgent, OPGGWorker, ResearchWorker, or OP.GG hWorker) AND it provides a substantive answer to the user's question → return **FINISH**.
2. **Data over opinion**: If the user asks for stats, builds, or ranks, ALWAYS pick **OPGGWorker** — even if the question is phrased casually.
3. **Ambiguous requests**: When in doubt between OPGGWorker and ResearchWorker, prefer **OPGGWorker** (data is more reliable).

## EXAMPLES
- "hey whats up" → GeneralAgent
- "what does yasuo's passive do?" → ResearchWorker
- "tell me about jinx's lore" → ResearchWorker
- "best build for jinx adc" → OPGGWorker
- "is darius op right now?" → ResearchWorker
- "faker's rank in korea" → OPGGWorker
- "what do people think about the new patch?" → ResearchWorker
- "top 5 mid laners this patch" → OPGGWorker
- "who counters zed and why" → OPGGWorker (data first, then advice)
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="messages"),
])

supervisor_chain = prompt | llm.with_structured_output(Router)

def supervisor_node(state):
    decision = supervisor_chain.invoke({"messages": state["messages"]})
    return {"next_node": decision.next_node}