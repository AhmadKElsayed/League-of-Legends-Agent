import os
import sqlite3
import logging
import logging.config
import aiosqlite
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.agent.graph import workflow, lol_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
os.makedirs("logs", exist_ok=True)

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)-20s | %(module)s.%(funcName)s:%(lineno)d | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/sessions.log",
            "maxBytes": 5_242_880,          # 5 MB per file
            "backupCount": 3,               # keep 3 rotated backups
            "formatter": "standard",
            "encoding": "utf-8",
        },
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        # Application logger — capture all operational events
        "lol_agent": {
            "level": "INFO",
            "handlers": ["file", "console"],
            "propagate": False,
        },
        # Silence noisy third-party libraries
        "aiosqlite":          {"level": "WARNING", "handlers": ["file"], "propagate": False},
        "httpcore":           {"level": "WARNING", "handlers": ["file"], "propagate": False},
        "httpcore.connection":{"level": "WARNING", "handlers": ["file"], "propagate": False},
        "httpcore.http11":    {"level": "WARNING", "handlers": ["file"], "propagate": False},
        "httpx":              {"level": "WARNING", "handlers": ["file"], "propagate": False},
    },
    "root": {
        "level": "WARNING",
        "handlers": ["file"],
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("lol_agent")

# Global variables for async memory
db_conn = None
agent = lol_agent # Default fallback

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_conn, agent
    try:
        # Create an async connection to the SQLite DB
        db_conn = await aiosqlite.connect("memory.db", check_same_thread=False)
        memory = AsyncSqliteSaver(db_conn)
        
        # This creates the checkpoints table if it doesn't exist
        await memory.setup()
        
        # Compile the workflow with the async memory checkpointer
        agent = workflow.compile(checkpointer=memory)
        logger.info("AsyncSqliteSaver successfully initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize memory: {e}")
        
    yield
    
    if db_conn:
        await db_conn.close()

app = FastAPI(title="League of Legends Agent API", lifespan=lifespan)

class ChatRequest(BaseModel):
    message: str
    thread_id: str

class ChatResponse(BaseModel):
    response: str

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    logger.info(f"Session {request.thread_id} - New Message: {request.message}")
    initial_state = {"messages": [HumanMessage(content=request.message)]}
    config = {"configurable": {"thread_id": request.thread_id}}
    
    final_state = None
    try:
        async for s in agent.astream(initial_state, config, stream_mode="values"):
            final_state = s
            
        final_message = final_state["messages"][-1].content
        if isinstance(final_message, list):
            text_parts = [part.get("text", "") for part in final_message if isinstance(part, dict) and part.get("type") == "text"]
            final_message = "\n".join(text_parts)
            
        logger.info(f"Session {request.thread_id} - Agent Reply: {str(final_message)[:100]}...")
        return ChatResponse(response=str(final_message))
        
    except Exception as e:
        logger.error(f"Session {request.thread_id} - Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions")
async def get_sessions():
    """Fetch all unique thread IDs from the sqlite checkpointer"""
    try:
        if not os.path.exists("memory.db"):
            return {"sessions": []}
            
        conn = sqlite3.connect("memory.db")
        cursor = conn.cursor()
        
        # Extract thread IDs
        cursor.execute("SELECT DISTINCT thread_id FROM checkpoints")
        rows = cursor.fetchall()
        
        sessions = []
        for row in rows:
            thread_id = row[0]
            config = {"configurable": {"thread_id": thread_id}}
            try:
                state = await agent.aget_state(config)
                messages = state.values.get("messages", [])
                
                preview = "Empty Chat"
                if messages:
                    # Find the first user message for a preview
                    for m in messages:
                        if isinstance(m, HumanMessage):
                            content = m.content
                            if isinstance(content, list):
                                text_parts = [part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"]
                                content = " ".join(text_parts)
                            preview = str(content)[:30] + "..."
                            break
                            
                if preview != "Empty Chat":
                    sessions.append({"thread_id": thread_id, "preview": preview})
            except Exception as e:
                logger.error(f"Error fetching state for {thread_id}: {e}")
                sessions.append({"thread_id": thread_id, "preview": "Chat Session"})
                
        conn.close()
        return {"sessions": sessions}
    except Exception as e:
        logger.error(f"Error fetching sessions: {str(e)}")
        return {"sessions": []}

@app.get("/api/sessions/{thread_id}")
async def get_session_history(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    state = await agent.aget_state(config)
    messages = state.values.get("messages", [])
    
    formatted_messages = []
    for msg in messages:
        content = msg.content
        if isinstance(content, list):
            text_parts = [part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"]
            content = "\n".join(text_parts)
            
        if isinstance(msg, HumanMessage):
            formatted_messages.append({"type": "human", "content": str(content)})
        elif isinstance(msg, AIMessage):
            formatted_messages.append({"type": "agent", "content": str(content)})
        elif isinstance(msg, SystemMessage):
            formatted_messages.append({"type": "system", "content": str(content)})
            
    return {"messages": formatted_messages}

@app.delete("/api/sessions/{thread_id}")
async def delete_session(thread_id: str):
    global db_conn
    try:
        if db_conn:
            await db_conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
            await db_conn.execute("DELETE FROM checkpoint_blobs WHERE thread_id = ?", (thread_id,))
            await db_conn.execute("DELETE FROM checkpoint_writes WHERE thread_id = ?", (thread_id,))
            await db_conn.commit()
            return {"status": "success"}
        else:
            raise Exception("Database connection not initialized")
    except Exception as e:
        logger.error(f"Error deleting session {thread_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "healthy", "components": ["fastapi", "langgraph", "mcp"]}

# Mount static files at root for the UI
app.mount("/", StaticFiles(directory="static", html=True), name="static")