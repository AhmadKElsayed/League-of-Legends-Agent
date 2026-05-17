import logging
from langchain_core.messages import AIMessage

logger = logging.getLogger("lol_agent")

def log_session_header(thread_id: str, message: str):
    logger.info("=" * 80)
    logger.info(f"🚀 SESSION START | Thread ID: {thread_id}")
    logger.info(f"💬 User Input: {message}")
    logger.info("=" * 80)

def log_node_transition(from_node: str, to_node: str):
    logger.info(f"🔄 Router transition: {from_node} ➔ {to_node}")

def log_llm_response(node_name: str, response: AIMessage):
    logger.info(f"🤖 [{node_name}] LLM Invocation:")
    
    # 1. Extract model name
    model_name = response.response_metadata.get("model_name") or "unknown-model"
    logger.info(f"   | Model: {model_name}")
    
    # 2. Extract token usage
    usage = response.usage_metadata or {}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    total_tokens = usage.get("total_tokens")
    
    if input_tokens is None or output_tokens is None:
        token_usage = response.response_metadata.get("token_usage") or {}
        input_tokens = token_usage.get("prompt_tokens") or token_usage.get("input_tokens")
        output_tokens = token_usage.get("completion_tokens") or token_usage.get("output_tokens")
        total_tokens = token_usage.get("total_tokens")
        
    if input_tokens is not None:
        logger.info(f"   | Token Usage: Input: {input_tokens} | Output: {output_tokens} | Total: {total_tokens}")
    else:
        logger.info("   | Token Usage: Not provided in response metadata")
        
    # 3. Extract thinking / reasoning process (e.g. from DeepSeek R1 or similar reasoning models)
    reasoning = (
        response.additional_kwargs.get("reasoning_content") or 
        response.additional_kwargs.get("reasoning") or 
        response.response_metadata.get("reasoning_content")
    )
    if reasoning:
        logger.info("   | 💭 Thinking Process:")
        for line in str(reasoning).strip().split("\n"):
            logger.info(f"   |   {line}")
            
    # 4. Content or tool calls
    if response.content:
        logger.info("   | 📄 Response Content:")
        for line in str(response.content).strip().split("\n"):
            logger.info(f"   |   {line}")
            
    if response.tool_calls:
        logger.info("   | 🛠️ Tool Calls requested:")
        for tc in response.tool_calls:
            logger.info(f"   |   - Tool: {tc['name']} (ID: {tc['id']})")
            logger.info(f"   |     Args: {tc['args']}")
    logger.info("-" * 80)

def log_tool_result(node_name: str, tool_name: str, tool_call_id: str, result_content: str):
    logger.info(f"🛠️ [{node_name}] Tool Executed: {tool_name} (ID: {tool_call_id})")
    
    # Trim output to avoid huge log clutter, but keep it informative
    max_log_len = 1000
    trimmed = str(result_content)
    if len(trimmed) > max_log_len:
        trimmed = trimmed[:max_log_len] + f"\n   |   ... [truncated {len(result_content) - max_log_len} chars] ..."
        
    logger.info("   | 📥 Output:")
    for line in trimmed.strip().split("\n"):
        logger.info(f"   |   {line}")
    logger.info("-" * 80)

def log_session_footer(thread_id: str, final_reply: str):
    logger.info("=" * 80)
    logger.info(f"🏁 SESSION END | Thread ID: {thread_id}")
    logger.info(f"✨ Final Agent Reply: {final_reply[:150]}...")
    logger.info("=" * 80)
