from fastapi import FastAPI
from .src.routers.routers import api_router
from contextlib import asynccontextmanager
from app.src.core.app_state import app_state
from app.src.graph.flow import build_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_state.graph = build_graph()
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(api_router)

