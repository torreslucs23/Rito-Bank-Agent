from fastapi import APIRouter, Query
from app.src.services.model_service import get_model_message


chat_router = APIRouter()

@chat_router.post("/message")
async def send_message(query: str):
    
    return {"response": await get_model_message(query)}
    