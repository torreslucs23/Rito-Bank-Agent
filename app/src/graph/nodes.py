from langgraph.graph import StateGraph
from typing import Annotated, Literal, TypedDict, Optional
from langgraph.graph.message import add_messages
from app.src.llm.llm import llm
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END, START



class AgentState(TypedDict):
    """State shared across all agents in the graph. """
    
    #conversation messages
    messages: Annotated[list, add_messages]
    
    # Auth data
    cpf_input: Optional[str]
    data_nascimento_input: Optional[str]
    autenticado: bool
    tentativas_autenticacao: int
    
    client: Optional[dict]
    
    #flow control
    next_agent: Optional[dict]
    finish: bool
    
    interview_data: Optional[dict]
    last_request: Optional[dict]
    
    


def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor: analisa mensagem e decide se chama triagem ou responde direto
    """
    messages = state["messages"]
    last_user_msg = messages[-1].content if messages else ""
    
    system_prompt = f"""Você é um supervisor de atendimento bancário.

Analise a mensagem do cliente:

Se o cliente disser explicitamente:
- "quero triagem"
- "fazer triagem" 
- "preciso de triagem"
- "iniciar triagem"
Ou variações similares → responda APENAS: TRIAGE

Para QUALQUER outra mensagem (saudações, perguntas, despedidas, etc) → responda APENAS: DIRECT

Mensagem do cliente: "{last_user_msg}"

Responda APENAS UMA PALAVRA (TRIAGE ou DIRECT):"""

    response = llm.invoke([SystemMessage(content=system_prompt)])
    
    # Parse da decisão
    decision = response.content.strip().upper()
    
    print(f" Supervisor decidiu: {decision}")
    
    if "TRIAGE" in decision:
        print("   → Redirecionando para agente de triagem")
        state['next_agent'] = 'triage_agent'
        state['waiting_for_agent'] = True
    else:
        print("   → Respondendo diretamente e finalizando")
        
        # Gera resposta direta e amigável
        direct_prompt = f"""Você é um atendente bancário simpático.

Cliente disse: "{last_user_msg}"

Responda de forma breve e cordial."""

        direct_response = llm.invoke([SystemMessage(content=direct_prompt)])
        
        state['messages'].append(AIMessage(content=direct_response.content))
        state['finish'] = True
        state['next_agent'] = None
        
def triage_node(state: AgentState) -> AgentState:
    """
    Triage Agent: Handles authentication
    """
    print(" TRIAGE AGENT activated  novo")
    
    state['next_agent'] = END
    return state
    