from fastapi import HTTPException
from datetime import date
from app.src.models.AgentStateModel import AgentStateModel
from app.src.llm.llm import llm
from app.src.core.app_state import app_state
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage



async def get_model_message(query: str) -> AgentStateModel | str:
    state1 = {
    "messages": [HumanMessage(content=query)],
    "cpf_input": None,
    "data_nascimento_input": None,
    "autenticado": False,
    "tentativas_autenticacao": 0,
    "client": None,
    "next_agent": None,
    "finish": False,
    "interview_data": None,
    "last_request": None
}
    return app_state.graph.invoke(state1)["messages"][-1].content