import os
from langchain_openrouter import ChatOpenRouter
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel
from typing import Literal

llm = ChatOpenRouter(model="deepseek/deepseek-v4-flash", temperature=0.1)
# llm = ChatOllama(
#     model="qwen2.5:72b", 
#     temperature=0,
#     base_url=os.getenv("OLLAMA_BASE_URL")
# )

class Router(BaseModel):
    next_node: Literal["FINISH", "GeneralAgent", "OPGGWorker", "ResearchWorker"]

system_prompt = (
    "You are a routing supervisor for a League of Legends AI team. "
    "Review the conversation history and decide who acts next:\n"
    "- GeneralAgent: Casual chat, lore, greetings.\n"
    "- OPGGWorker: Hard data, win rates, optimal builds, player ranks, match history.\n"
    "- ResearchWorker: Subjective advice, niche matchups, community opinions, web research.\n"
    "\n"
    "CRITICAL RULES FOR PREVENTING LOOPS:\n"
    "1. Look at the LAST message in the conversation.\n"
    "2. If the LAST message is from one of your workers (e.g., GeneralAgent, OPGGWorker) AND it successfully answers the user's prompt, you MUST respond with 'FINISH'.\n"
    "3. Only route to a worker if the user's request has NOT been answered yet, or if a multi-part question requires a different worker."
)

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="messages"),
])

supervisor_chain = prompt | llm.with_structured_output(Router)

def supervisor_node(state):
    decision = supervisor_chain.invoke({"messages": state["messages"]})
    return {"next_node": decision.next_node}