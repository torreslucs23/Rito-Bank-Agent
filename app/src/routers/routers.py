from fastapi import APIRouter

from .chat_router import chat_router

api_router = APIRouter()
"""
Main API router that aggregates all sub-routers of the project:
home, clients, products, orders, and payments.
"""

api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
