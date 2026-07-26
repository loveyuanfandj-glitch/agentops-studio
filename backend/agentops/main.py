from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentops.api import router
from agentops.config import get_settings
from agentops.database import SessionFactory, create_schema
from agentops.logging import configure_logging
from agentops.observability import configure_tracing
from agentops.providers import build_provider
from agentops.seed import seed_demo_data
from agentops.tools import ToolRegistry

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    configure_tracing(settings)
    if settings.app_env != "production":
        await create_schema()
    if settings.seed_demo_data:
        async with SessionFactory() as session:
            await seed_demo_data(session)
    app.state.settings = settings
    app.state.provider = build_provider(settings)
    app.state.tools = ToolRegistry(
        timeout_seconds=settings.tool_timeout_seconds,
        retry_attempts=settings.tool_retry_attempts,
    )
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Multi-tenant orchestration, guardrails and observability for tool-using agents.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
