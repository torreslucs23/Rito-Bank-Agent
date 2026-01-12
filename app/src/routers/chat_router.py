from fastapi import APIRouter

from app.src.services.model_service import get_model_message

chat_router = APIRouter()


@chat_router.post("/message")
async def send_message(query: str):
    # try:
    return {"response": await get_model_message(query)}
    # except Exception as e:
    # raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno do servidor")
