import os
import json
import sqlite3
import logging
import logging.config
import pathlib
import aiosqlite
import asyncio
from contextlib import asynccontextmanager, AsyncExitStack
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from dotenv import load_dotenv

from app.agent.graph import workflow, lol_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.agent_logger import log_session_header, log_session_footer

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from app.agent.nodes.opgg_worker import set_persistent_session, clear_persistent_session

dotenv_path = pathlib.Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

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
    exit_stack = AsyncExitStack()
    try:
        # Create an async connection to the SQLite DB
        os.makedirs("data", exist_ok=True)
        db_conn = await aiosqlite.connect("data/memory.db", check_same_thread=False)
        await db_conn.execute("PRAGMA journal_mode=WAL;")
        memory = AsyncSqliteSaver(db_conn)
        
        # This creates the checkpoints table if it doesn't exist
        await memory.setup()
        
        # Setup session metadata table for custom session names
        await db_conn.execute("""
            CREATE TABLE IF NOT EXISTS session_metadata (
                thread_id TEXT PRIMARY KEY,
                custom_name TEXT
            )
        """)
        await db_conn.commit()
        
        # Compile the workflow with the async memory checkpointer
        agent = workflow.compile(checkpointer=memory)
        logger.info("AsyncSqliteSaver successfully initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize memory: {e}")

    # Initialize Persistent MCP Session
    try:
        possible_paths = [
            os.getenv("OPGG_MCP_PATH"),
            "./opgg-mcp/dist/index.js",
            "../opgg-mcp/dist/index.js"
        ]
        opgg_server_path = next((p for p in possible_paths if p and pathlib.Path(p).exists()), None)
        
        if opgg_server_path:
            logger.info(f"Initializing persistent MCP session with: {opgg_server_path}")
            mcp_client = MultiServerMCPClient({
                "opgg": {
                    "transport": "stdio",
                    "command": "node",
                    "args": [opgg_server_path]
                }
            })
            
            # Enter the session context and store references
            session = await exit_stack.enter_async_context(mcp_client.session("opgg"))
            
            # Pre-load tools
            all_tools = await load_mcp_tools(session)
            lol_tools = [t for t in all_tools if t.name.startswith("lol_")]
            
            await set_persistent_session(session, mcp_client, lol_tools)
            logger.info(f"Persistent MCP session successfully initialized with {len(lol_tools)} tools.")
        else:
            logger.warning("OPGG MCP server path not found. Persistent MCP session skipped.")
    except Exception as e:
        logger.error(f"Failed to initialize persistent MCP session: {e}")
        
    try:
        yield
    finally:
        logger.info("Closing persistent database connection and MCP sessions...")
        await clear_persistent_session()
        await exit_stack.aclose()
        if db_conn:
            await db_conn.close()
        logger.info("Shutdown cleanup complete.")

app = FastAPI(title="League of Legends Agent API", lifespan=lifespan)

class ChatRequest(BaseModel):
    message: str
    thread_id: str

class ChatResponse(BaseModel):
    response: str

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    log_session_header(request.thread_id, request.message)
    initial_state = {"messages": [HumanMessage(content=request.message)]}
    config = {"configurable": {"thread_id": request.thread_id}}
    
    async def event_generator():
        accumulated_text = ""
        try:
            async for event in agent.astream_events(initial_state, config, version="v2"):
                kind = event["event"]
                name = event["name"]
                metadata = event.get("metadata", {})
                node = metadata.get("langgraph_node")
                
                # 1. Yield active node changes for status updates
                if kind == "on_chain_start" and node:
                    yield f"event: status\ndata: {json.dumps({'node': node})}\n\n"
                
                # 2. Yield token streams from the active worker generating answer text
                elif kind == "on_chat_model_stream":
                    if node in ["GeneralAgent", "OPGGWorker", "ResearchWorker"]:
                        chunk = event["data"]["chunk"]
                        if chunk.content:
                            accumulated_text += chunk.content
                            yield f"event: token\ndata: {json.dumps({'text': chunk.content})}\n\n"
                            
                # 3. Yield tool execution logs
                elif kind == "on_tool_start":
                    tool_name = name
                    yield f"event: tool_log\ndata: {json.dumps({'status': 'start', 'tool': tool_name})}\n\n"
                    
                elif kind == "on_tool_end":
                    tool_name = name
                    yield f"event: tool_log\ndata: {json.dumps({'status': 'end', 'tool': tool_name})}\n\n"
            
            log_session_footer(request.thread_id, accumulated_text)
            yield "event: done\ndata: {}\n\n"
            
        except asyncio.CancelledError:
            logger.info(f"Session {request.thread_id} - Client disconnected during stream.")
            raise
        except Exception as e:
            logger.exception(f"Session {request.thread_id} - Streaming Error:")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/sessions")
async def get_sessions():
    """Fetch all unique thread IDs from the sqlite checkpointer"""
    try:
        if not os.path.exists("data/memory.db"):
            return {"sessions": []}
            
        conn = sqlite3.connect("data/memory.db")
        cursor = conn.cursor()
        
        # Extract thread IDs sorted by recency
        cursor.execute("""
            SELECT c.thread_id, m.custom_name
            FROM checkpoints c
            LEFT JOIN session_metadata m ON c.thread_id = m.thread_id
            GROUP BY c.thread_id 
            ORDER BY max(c.rowid) DESC
        """)
        rows = cursor.fetchall()
        
        sessions = []
        for row in rows:
            thread_id = row[0]
            custom_name = row[1]
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
                            
                if preview != "Empty Chat" or custom_name:
                    sessions.append({
                        "thread_id": thread_id, 
                        "preview": preview,
                        "custom_name": custom_name
                    })
            except Exception as e:
                logger.error(f"Error fetching state for {thread_id}: {e}")
                sessions.append({"thread_id": thread_id, "preview": "Chat Session", "custom_name": custom_name})
                
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
            
        content_str = str(content).strip() if content else ""
            
        if isinstance(msg, HumanMessage):
            if content_str:
                formatted_messages.append({"type": "human", "content": content_str})
        elif isinstance(msg, AIMessage):
            tool_calls = getattr(msg, 'tool_calls', [])
            for tool_call in tool_calls:
                formatted_messages.append({"type": "tool_log", "tool_name": tool_call["name"]})
            if content_str:
                formatted_messages.append({"type": "agent", "content": content_str})
        elif isinstance(msg, SystemMessage):
            pass
            
    return {"messages": formatted_messages}

class RenameRequest(BaseModel):
    name: str

@app.put("/api/sessions/{thread_id}/rename")
async def rename_session(thread_id: str, request: RenameRequest):
    global db_conn
    try:
        if db_conn:
            await db_conn.execute("""
                INSERT INTO session_metadata (thread_id, custom_name)
                VALUES (?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET custom_name = excluded.custom_name
            """, (thread_id, request.name))
            await db_conn.commit()
            return {"status": "success", "custom_name": request.name}
        else:
            raise Exception("Database connection not initialized")
    except Exception as e:
        logger.error(f"Error renaming session {thread_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/sessions/{thread_id}")
async def delete_session(thread_id: str):
    global db_conn
    try:
        if db_conn:
            await db_conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
            await db_conn.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
            await db_conn.execute("DELETE FROM session_metadata WHERE thread_id = ?", (thread_id,))
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
frontend_path = pathlib.Path(__file__).parent.parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="static")