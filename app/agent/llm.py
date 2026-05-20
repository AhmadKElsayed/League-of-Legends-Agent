import os
from langchain_openrouter import ChatOpenRouter

def get_llm(model_name: str, temperature: float = 0.2, max_tokens: int = None) -> ChatOpenRouter:
    api_key = os.getenv("OPENROUTER_API_KEY")
    return ChatOpenRouter(
        model=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        openrouter_api_key=api_key
    )
