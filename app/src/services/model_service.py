from fastapi import HTTPException
from datetime import date
from app.src.models.AgentStateModel import AgentStateModel
from app.src.llm.llm import llm


async def get_model_message(query: str) -> AgentStateModel | str:
    return llm.invoke(query).content