import logging

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.graph import END

from app.src.graph.state import AgentState
from app.src.llm.base_llm import llm
from app.src.llm.prompts import (
    SYSTEM_PROMPT_BANK,
    SYSTEM_PROMPT_FINAL_INSTRUCTION,
    TRIAGE_PROMPT,
)
from app.src.llm.tools import save_birth_date, save_cpf
from app.src.llm.triage_llm import triage_llm
from app.src.services.user_service import authenticate_user

logger = logging.getLogger(__name__)


def triage_node(state: AgentState) -> AgentState:
    """
    Triage Agent: Handles authentication
    """
    logger.info("Entering Triage Agent Node")

    messages = state["messages"]
    recent_messages = messages[-20:] if len(messages) > 20 else messages

    if not state.get("cpf_input"):
        system_prompt = f"""{SYSTEM_PROMPT_BANK}
{TRIAGE_PROMPT}

Your current context is to collect the customer's CPF for authentication.
Objective: Collect CPF (11 digits).

Instructions:
- If CPF provided -> CALL `save_cpf`.
- If not provided -> Ask politely.
- Only accept valid CPFs (11 digits).

{SYSTEM_PROMPT_FINAL_INSTRUCTION}
REMEMBER: Respond in Portuguese.
"""
        try:
            response = triage_llm.invoke(
                [SystemMessage(content=system_prompt), *recent_messages],
                max_tokens=100,
                temperature=0.3,
            )
        except Exception as e:
            logger.error(f"Error in Triage LLM invocation: {e}")
            response = AIMessage(
                content="Desculpe, ocorreu um erro ao processar sua solicitação. Tente novamente mais tarde."
            )

        if response.tool_calls:
            tool_call = response.tool_calls[0]
            cpf_result = save_cpf.invoke(tool_call["args"])

            if not cpf_result["success"]:
                state["messages"].extend(
                    [
                        response,
                        ToolMessage(
                            content=str(cpf_result), tool_call_id=tool_call["id"]
                        ),
                    ]
                )

                prompt = f"""{SYSTEM_PROMPT_BANK}
                    The provided CPF is invalid. Please inform a valid CPF with 11 digits politely.
                    {SYSTEM_PROMPT_FINAL_INSTRUCTION}"""

                response_llm = llm.invoke(
                    [SystemMessage(content=prompt), *recent_messages], max_tokens=50
                )

                state["messages"].append(AIMessage(content=response_llm.content))
                state["next_agent"] = END
                return state

            state["cpf_input"] = cpf_result["cpf"]
            state["messages"].extend(
                [
                    response,
                    ToolMessage(content=str(cpf_result), tool_call_id=tool_call["id"]),
                ]
            )

            prompt = f"""{SYSTEM_PROMPT_BANK}
                CPF saved. Confirm politely and ask for DATE OF BIRTH briefly.
                {SYSTEM_PROMPT_FINAL_INSTRUCTION}"""

            final_response = llm.invoke(
                [SystemMessage(content=prompt), *recent_messages], max_tokens=50
            )
            state["messages"].append(AIMessage(content=final_response.content))

        else:
            state["messages"].append(response)

    elif not state.get("birth_date"):
        system_prompt = f"""{SYSTEM_PROMPT_BANK}
{TRIAGE_PROMPT}

Context: CPF collected: {state["cpf_input"]}
Objective: Collect DATE OF BIRTH.

Instructions:
- If date provided -> CALL `save_birth_date`.
- If not -> Ask politely.

{SYSTEM_PROMPT_FINAL_INSTRUCTION}
REMEMBER: Respond in Portuguese.
"""
        try:
            response = triage_llm.invoke(
                [SystemMessage(content=system_prompt), *recent_messages],
                max_tokens=100,
                temperature=0.3,
            )
        except Exception as e:
            logger.error(f"Error in Triage LLM invocation: {e}")
            response = AIMessage(
                content="Desculpe, ocorreu um erro ao processar sua solicitação. Tente novamente mais tarde."
            )

        if response.tool_calls:
            tool_call = response.tool_calls[0]
            birth_date_result = save_birth_date.invoke(tool_call["args"])

            if birth_date_result["success"]:
                user_is_authenticated = authenticate_user(
                    state["cpf_input"], birth_date_result["birth_date"]
                )

                if not user_is_authenticated["authenticated"]:
                    state["authentication_attempts"] += 1
                    if state["authentication_attempts"] >= 3:
                        state["messages"].append(
                            AIMessage(
                                content="Número máximo de tentativas atingido. Encerrando atendimento."
                            )
                        )
                        return {
                            **state,
                            "next_agent": END,
                            "birth_date": None,
                            "cpf_input": None,
                        }
                    else:
                        state["messages"].append(
                            AIMessage(
                                content="Autenticação falhou. Dados incorretos. Reiniciando processo."
                            )
                        )
                        return {**state, "birth_date": None, "cpf_input": None}

                state["birth_date"] = birth_date_result["birth_date"]
                state["messages"].extend(
                    [
                        response,
                        ToolMessage(
                            content=str(birth_date_result), tool_call_id=tool_call["id"]
                        ),
                    ]
                )

                prompt = f"""{SYSTEM_PROMPT_BANK}
                    Authentication successful. Confirm to customer politely. Be brief.
                    {SYSTEM_PROMPT_FINAL_INSTRUCTION}"""

                try:
                    final_response = llm.invoke(
                        [SystemMessage(content=prompt), *recent_messages],
                        max_tokens=100,
                        temperature=0.3,
                    )
                except Exception as e:
                    logger.error(f"Error in LLM invocation: {e}")
                    final_response = AIMessage(
                        content="Desculpe, ocorreu um erro ao processar sua solicitação. Tente novamente mais tarde."
                    )

                state["messages"].append(AIMessage(content=final_response.content))
                state["authenticated"] = True
                return state
            else:
                state["messages"].append(response)
                try:
                    retry_resp = llm.invoke(
                        f"""{SYSTEM_PROMPT_BANK} Invalid date. Ask again politely. {SYSTEM_PROMPT_FINAL_INSTRUCTION}""",
                        max_tokens=50,
                        temperature=0.2,
                    )
                except Exception as e:
                    logger.error(f"Error in LLM invocation: {e}")
                    retry_resp = AIMessage(
                        content="Desculpe, ocorreu um erro ao processar sua solicitação. Tente novamente mais tarde."
                    )

                state["messages"].append(AIMessage(content=retry_resp.content))
        else:
            state["messages"].append(response)

    state["next_agent"] = END
    return state
