import os
from langchain_openrouter import ChatOpenRouter
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

def get_llm(model_name: str, temperature: float = 0.2, max_tokens: int = None) -> ChatOpenRouter:
    api_key = os.getenv("OPENROUTER_API_KEY")
    return ChatOpenRouter(
        model=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        openrouter_api_key=api_key
    )

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
async def invoke_with_retry(agent, messages):
    """Robustness wrapper for LLM invocations with exponential backoff."""
    return await agent.ainvoke(messages)
