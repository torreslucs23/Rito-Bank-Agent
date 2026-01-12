import logging

from langchain_core.messages import AIMessage, SystemMessage

from app.src.graph.state import AgentState
from app.src.llm.currency_llm import currency_llm
from app.src.llm.prompts import SYSTEM_PROMPT_BANK, SYSTEM_PROMPT_FINAL_INSTRUCTION

logger = logging.getLogger(__name__)


def currency_agent_node(state: AgentState) -> AgentState:
    """
    Currency Exchange Agent
    """
    logger.info("Entering Currency Agent Node")

    messages = (
        state["messages"][-10:] if len(state["messages"]) > 10 else state["messages"]
    )

    system_prompt = f"""{SYSTEM_PROMPT_BANK}
    You are an expert trader and currency exchange assistant.
    Your `get_exchange_rate_tool` tool provides quotes relative to the REAL (BRL).

    MANDATORY EXECUTION STRATEGY:
    1. Before calling tool, LOOK AT HISTORY.
    2. If value exists in 'ToolMessage', DON'T CALL AGAIN. Calculate directly.
    
    CASE 1: Quote to Real -> Call tool.
    CASE 2: Foreign to Foreign -> Call tool A, Call tool B -> Wait -> Calculate.

    At the end, respond directly.
    {SYSTEM_PROMPT_FINAL_INSTRUCTION}
    REMEMBER: Respond in Portuguese.
    """

    try:
        response = currency_llm.invoke(
            [SystemMessage(content=system_prompt), *messages],
            temperature=0.4,
            max_tokens=150,
        )
    except Exception as e:
        logger.error(f"Error in Currency Agent LLM invocation: {e}")
        response = AIMessage(
            content="Desculpe, ocorreu um erro ao processar sua solicitação. Tente novamente mais tarde."
        )
    return {"messages": [response]}
