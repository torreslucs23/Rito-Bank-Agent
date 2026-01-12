from fastapi import HTTPException
from datetime import date
from app.src.models.AgentStateModel import AgentStateModel
from app.src.llm.base_llm import llm
from app.src.core.app_state import app_state
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.src.core.app_state import app_state

state1 = {
    "messages": [],
    "cpf_input": '12345678900',
    "birth_date": '1990-05-15',
    "authenticated": True,
    "authentication_attempts": 0,
    "next_agent": None,
    "finish": False,
}

async def get_model_message(query: str) -> AgentStateModel | str:
    global state1

    state1["messages"].append(HumanMessage(content=query))
    # try:
    state1 = app_state.graph.invoke(state1)
    # except Exception as e:
        # raise HTTPException(status_code=500, detail=str(e))
    return state1["messages"][-1].content