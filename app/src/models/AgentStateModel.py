from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field
from langchain_core.messages import BaseMessage


class AgentStateModel(SQLModel):
    """
    Estado compartilhado entre os agentes.
    Usado como DTO de entrada (FastAPI) e como estado inicial do LangGraph.
    """

    # Conversation
    messages: List[BaseMessage] = Field(default_factory=list)

    # Auth data
    cpf_input: Optional[str] = None
    data_nascimento_input: Optional[str] = None
    autenticado: bool = False
    tentativas_autenticacao: int = 0

    # Client data (após autenticação)
    client: Optional[Dict[str, Any]] = None

    # Flow control
    next_agent: Optional[Dict[str, Any]] = None
    finish: bool = False

    # Interview / business context
    interview_data: Optional[Dict[str, Any]] = None
    last_request: Optional[Dict[str, Any]] = None
