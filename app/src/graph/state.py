from typing import Annotated, TypedDict, Optional, List
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """State shared across all agents in the graph."""
    # conversation messages
    messages: Annotated[List, add_messages]
    
    # Auth data
    cpf_input: Optional[str]
    birth_date: Optional[str]
    authenticated: bool
    authentication_attempts: int
    
    # flow control
    next_agent: Optional[str]
    
    # interview credit
    credit_interview: bool
    