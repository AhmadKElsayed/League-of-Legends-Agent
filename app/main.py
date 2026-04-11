from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.agent.graph import lol_agent
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="League of Legends Agent API")

class ChatRequest(BaseModel):
    message: str
    thread_id: str

class ChatResponse(BaseModel):
    response: str

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    initial_state = {"messages": [HumanMessage(content=request.message)]}
    config = {"configurable": {"thread_id": request.thread_id}}
    
    final_state = None
    try:
        async for s in lol_agent.astream(initial_state, config, stream_mode="values"):
            final_state = s
            
        final_message = final_state["messages"][-1].content
        return ChatResponse(response=final_message)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "healthy", "components": ["fastapi", "langgraph", "mcp"]}