from fastapi import APIRouter, Query
from app.src.models.AgentStateModel import AgentStateModel
from app.src.services.model_service import get_model_message


chat_router = APIRouter()

@chat_router.post("/message")
async def send_message(query: str, state: AgentStateModel):
    
    return {"response": await get_model_message(query)}
    