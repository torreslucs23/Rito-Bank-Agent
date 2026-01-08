from langgraph.graph import StateGraph
from typing import Annotated, Literal, TypedDict, Optional
from langgraph.graph.message import add_messages


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
    
    

