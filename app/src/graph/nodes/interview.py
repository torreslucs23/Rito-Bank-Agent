import json
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage

from app.src.graph.state import AgentState
from app.src.llm.base_llm import llm
from app.src.llm.interview_llm import interview_llm
from app.src.llm.tools import submit_credit_interview
from app.src.llm.prompts import SYSTEM_PROMPT_BANK, SYSTEM_PROMPT_FINAL_INSTRUCTION
import logging

logger = logging.getLogger(__name__)

def interview_agent_node(state: AgentState) -> AgentState:
    """
    Interview Agent: Conducts financial interview
    """
    logger.info("Entering Interview Agent Node")
    
    messages = state["messages"]
    cpf_user = state.get("cpf_input", "Unknown")
    last_message = messages[-1]

    if isinstance(last_message, ToolMessage):
        try:
            content = last_message.content
            data = json.loads(content) if isinstance(content, str) else content
            new_score = data.get("new_score", "N/A")
        except:
            new_score = "atualizado"

        system_prompt = f"""{SYSTEM_PROMPT_BANK}
        
        Interview successful! New score: {new_score}.
        
        MISSION:
        1. Thank customer.
        2. Inform score recalculated.
        3. Say: "Agora vou transferir você de volta para o Agente de Crédito para reanalisar seu pedido de limite."
        4. IMPORTANT: Use keyword "REDIRECT_CREDIT".
        
        {SYSTEM_PROMPT_FINAL_INSTRUCTION}
        REMEMBER: Respond in Portuguese.
        """
        try:
            response = llm.invoke([SystemMessage(content=system_prompt), *messages[-30:]])
        except Exception as e:
            logger.error(f"Error in Interview Agent LLM invocation: {e}")
            response = AIMessage(content="Desculpe, ocorreu um erro ao processar sua solicitação. Tente novamente mais tarde.")
        
        return {
            "messages": [response],
            "credit_interview": False
        }

    else:
        interview_llm_with_tools = interview_llm.bind_tools([submit_credit_interview])
        
        system_prompt = f"""{SYSTEM_PROMPT_BANK}
        
        You are the Credit Interview Agent.
        OBJECTIVE: Collect data for `submit_credit_interview`.
        
        REQUIRED DATA (Ask ONE at a time):
        1. Monthly Income (R$)
        2. Employment Type (Formal, Autonomous, Unemployed)
        3. Fixed Expenses (R$)
        4. Dependents
        5. Active Debts (Yes/No)
        
        INSTRUCTIONS:
        - Customer CPF: {cpf_user}
        - Don't ask all at once.
        - If answered all -> CALL TOOL.
        
        If user wants to quit: respond "ENCERRAR".
        
        {SYSTEM_PROMPT_FINAL_INSTRUCTION}
        REMEMBER: Respond in Portuguese.
        """
    
        try:
            response = interview_llm_with_tools.invoke([SystemMessage(content=system_prompt), *messages[-30:]])
        except Exception as e:
            logger.error(f"Error in Interview Agent LLM invocation: {e}")
            response = AIMessage(content="Desculpe, ocorreu um erro ao processar sua solicitação. Tente novamente mais tarde.")
        
        if "ENCERRAR" in response.content.upper():
            return {
                "messages": [AIMessage(content="Entendido. Encerrando o processo da entrevista")],
                "credit_interview": False
            }

        return {
            "messages": [response],
            "credit_interview": True
        }