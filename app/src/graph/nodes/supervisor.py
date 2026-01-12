import json
import logging

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END

from app.src.graph.state import AgentState
from app.src.llm.base_llm import llm
from app.src.llm.prompts import SYSTEM_PROMPT_BANK, SYSTEM_PROMPT_FINAL_INSTRUCTION

logger = logging.getLogger(__name__)


def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor: analyzes message and decides whether to call triage or respond directly
    """
    logger.info("Entering Supervisor Node")

    messages = state["messages"]
    recent_messages = messages[-20:] if len(messages) > 20 else messages

    if not state.get("authenticated"):
        state["next_agent"] = "triage_agent"
        return state

    if state.get("credit_interview"):
        state["next_agent"] = "interview_agent"
        return state

    system_prompt = f""" {SYSTEM_PROMPT_BANK}

Analyze the customer's message:

If the customer explicitly says they want to know the value of a currency, conversion or something similar:
- "qual a cotação do dólar?"
- "me informe o valor do euro"
- "qual o valor do bitcoin hoje?"
- "quero saber a cotação da libra"
Or similar variations → respond ONLY: CURRENCY

if the customer explicitly talks about "limit", "credit increase", "score", "credit card":
- "quero aumentar meu limite"
- "qual meu limite atual?"
- "liberar mais crédito"
or other similar variations → respond ONLY: CREDIT

if the customer explicitly wants to increase your credit with an interview:
- "quero fazer uma entrevista para aumentar meu limite"
- "gostaria de responder algumas perguntas para aumentar meu limite"
- "preciso aumentar meu limite de crédito"
→ respond ONLY: INTERVIEW

If the customer wants to EXIT, quit, say goodbye or end the conversation:
- "sair"
- "tchau"
- "encerrar atendimento"
- "obrigado, tchau"
- "fechar"
- "valeu, flw"
Or similar variations → respond ONLY: EXIT

For ANY other message (greetings, questions, farewells, etc) → respond ONLY: DIRECT

Customer's message: "{recent_messages[-1].content if recent_messages else ""}"

{SYSTEM_PROMPT_FINAL_INSTRUCTION}

Respond with ONLY ONE WORD (CURRENCY, CREDIT, INTERVIEW, EXIT or DIRECT):"""

    try:
        response = llm.invoke([SystemMessage(content=system_prompt), *recent_messages])
    except Exception as e:
        logger.error(f"Error in Supervisor LLM invocation: {e}")
        response = AIMessage(
            content="Desculpe, ocorreu um erro ao processar sua solicitação. Tente novamente mais tarde."
        )

    decision = response.content.strip().upper()

    if "CURRENCY" in decision:
        state["next_agent"] = "currency_agent"
        return state

    elif "CREDIT" in decision:
        state["next_agent"] = "credit_agent"
        return state

    elif "INTERVIEW" in decision:
        state["next_agent"] = "interview_agent"
        return state

    elif "EXIT" in decision:
        goodbye_message = AIMessage(
            content="O Rito Bank agradece seu contato! Sessão encerrada com segurança. Até a próxima!"
        )

        return {
            "messages": [goodbye_message],
            "authenticated": False,
            "cpf_input": None,
            "birth_date": None,
            "next_agent": END,
        }

    else:
        state_for_prompt = state.copy()
        state_for_prompt.pop("messages", None)

        state_context_str = json.dumps(state_for_prompt, indent=2, ensure_ascii=False)
        direct_prompt = f"""{SYSTEM_PROMPT_BANK}
        
        ROLE: You are a friendly banking assistant handling general conversation (Direct Interaction).
        OBJECTIVE: Respond politely and professionally to greetings, thanks, or random comments.
        CLIENT INFO: {state_context_str}

        INSTRUCTIONS:
        1. **Personalize:** Use client name if available.
        2. **Be Natural:** Respond to greeting/thanks.
        3. **No Auth Block:** Do NOT ask for CPF here.
        4. **Style:** Be brief, professional, and warm.
        
        {SYSTEM_PROMPT_FINAL_INSTRUCTION}
        """

        try:
            direct_response = llm.invoke(
                [SystemMessage(content=direct_prompt), *recent_messages],
                temperature=0.5,
                max_tokens=100,
            )
        except Exception as e:
            logger.error(f"Error in Supervisor LLM invocation: {e}")
            direct_response = AIMessage(
                content="Desculpe, ocorreu um erro ao processar sua solicitação. Tente novamente mais tarde."
            )

        state["messages"].append(AIMessage(content=direct_response.content))
        state["next_agent"] = END
        return state
