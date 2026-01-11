from fastapi import HTTPException
from datetime import date
from app.src.models.AgentStateModel import AgentStateModel
from app.src.llm.base_llm import llm
from app.src.core.app_state import app_state
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.src.core.app_state import app_state

state1 = {
    "messages": [],
    "cpf_input": None,
    "birth_date": None,
    "authenticated": False,
    "authentication_attempts": 0,
    "client": None,
    "next_agent": None,
    "finish": False,
    "interview_data": None,
    "last_request": None
}

async def get_model_message(query: str) -> AgentStateModel | str:
    global state1
    print(state1['messages'][-2].content if state1['messages'] else "No messages yet")

    state1["messages"].append(HumanMessage(content=query))
    
    state1 = app_state.graph.invoke(state1)
    return state1["messages"][-1].content