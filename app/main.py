from fastapi import FastAPI
from .src.routers.routers import api_router
from contextlib import asynccontextmanager
from app.src.core.app_state import app_state
from app.src.graph.flow import build_graph
from app.src.config.logging_config import setup_logging
import logging


setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    app_state.graph = build_graph()
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(api_router)

