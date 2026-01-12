from langchain_core.messages import SystemMessage, ToolMessage, AIMessage

from app.src.graph.state import AgentState
from app.src.llm.base_llm import llm
from app.src.llm.credit_llm import credit_llm
from app.src.llm.tools import process_limit_increase_request, get_score_and_or_limit
from app.src.llm.prompts import SYSTEM_PROMPT_BANK, SYSTEM_PROMPT_FINAL_INSTRUCTION
import logging

logger = logging.getLogger(__name__)

def credit_agent_node(state: AgentState) -> AgentState:
    """
    Credit Agent: Handles limit and score queries
    """
    logger.info("Entering Credit Agent Node")
    messages = state["messages"]
    
    client_context = f"""
    LOGGED CLIENT DATA:
    Name: {state.get('name', 'N/A')}
    CPF: {state.get('cpf_input', 'N/A')}
    Current Score: {state.get('score', 0)}
    Current Limit: R$ {state.get('credit_limit', 0)}
    """

    last_message = messages[-1]

    if isinstance(last_message, ToolMessage):
        tool_output = last_message.content.lower()
        
        if "status" in tool_output and ("aprovado" in tool_output or "rejeitado" in tool_output):
            is_rejected = "rejeitado" in tool_output
            
            if is_rejected:
                system_prompt = f"""{SYSTEM_PROMPT_BANK}
                You are a Credit Agent. Request REJECTED.
                
                MISSION:
                1. Inform rejection professionally.
                2. MANDATORY: Offer "Credit Profile Interview" YOURSELF.
                - Phrase: "If you wish, I can start a profile analysis interview now to try to adjust your score."
                3. If agreed: Respond "Vou iniciar a entrevista agora."
                
                {SYSTEM_PROMPT_FINAL_INSTRUCTION}
                Respond in Portuguese.
                """
            else:
                system_prompt = f"""{SYSTEM_PROMPT_BANK}
                Request APPROVED.
                MISSION: Congratulate and confirm new limit.
                {SYSTEM_PROMPT_FINAL_INSTRUCTION}
                Respond in Portuguese.
                """
            try:
                response = llm.invoke([SystemMessage(content=system_prompt), *messages[-10:]], temperature=0.3)
            except Exception as e:
                logger.error(f"Error in Credit Agent LLM invocation: {e}")
                response = AIMessage(content="Desculpe, ocorreu um erro ao processar sua solicitação. Tente novamente mais tarde.")
            return {"messages": [response]}

    credit_llm_with_tools = credit_llm.bind_tools([process_limit_increase_request, get_score_and_or_limit])
                
    system_prompt = f"""{SYSTEM_PROMPT_BANK}
    
    CLIENT CONTEXT: {client_context}
    
    RESPONSIBILITIES:
    1. Consult Limit/Score: Use `get_score_and_or_limit`.
    
    2. Limit Increase Request:
        - Check desired value.
        - If missing value -> Ask.
        - If present -> CALL `process_limit_increase_request`.
    
    3. If customer accepts Interview (after rejection):
        - Respond: "Vou iniciar a entrevista agora." (Router detects INTERVIEW).
        
    Be direct.
    {SYSTEM_PROMPT_FINAL_INSTRUCTION}
    Respond in Portuguese.
    """
    try:
        response = credit_llm_with_tools.invoke([SystemMessage(content=system_prompt), *messages[-10:]], temperature=0.3, max_tokens=300)
    except Exception as e:
        logger.error(f"Error in Credit Agent LLM invocation: {e}")
        response = AIMessage(content="Desculpe, ocorreu um erro ao processar sua solicitação. Tente novamente mais tarde.")
    
    return {"messages": [response]}