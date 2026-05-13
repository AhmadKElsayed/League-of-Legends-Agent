import os
from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter
from langchain_core.messages import SystemMessage

load_dotenv()

llm = ChatOpenRouter(model="deepseek/deepseek-v4-flash", temperature=0.4)

# llm = ChatOllama(
#     model="llama3.1", 
#     temperature=0,
#     base_url=os.getenv("OLLAMA_BASE_URL")
# )

def general_agent_node(state):
    system_message = SystemMessage(
        content="You are a friendly League of Legends assistant. Keep responses brief and engaging."
    )
    
    # Combine it cleanly with the state messages
    messages = [system_message] + list(state["messages"])
    
    response = llm.invoke(messages)
    return {"messages": [response]}