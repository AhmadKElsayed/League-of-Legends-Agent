import os
from dotenv import load_dotenv
load_dotenv()

from langchain_openrouter import ChatOpenRouter

llm = ChatOpenRouter(
    model="deepseek/deepseek-v4-flash",
    temperature=0.2,
    max_tokens=1000
)

print("llm.max_tokens:", llm.max_tokens)
print("llm.model_kwargs:", llm.model_kwargs)
