from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.agents.supervisor import build_graph
from src.api.routes import router
from src.knowledge.ingestion import setup_knowledge_base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the agent graph and populate the knowledge base at startup."""
    app.state.graph = build_graph()
    app.state.vector_store = setup_knowledge_base()
    yield


app = FastAPI(
    title="Predictive Maintenance Multi-Agent System",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
