from fastapi import APIRouter, Query

chat_router = APIRouter()

@chat_router.get("/message")
async def get_message(query: str ):
    return {"response": f"You sent: {query}"}
    