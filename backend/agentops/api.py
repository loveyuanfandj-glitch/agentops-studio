from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agentops.database import get_session
from agentops.orchestrator import AgentOrchestrator
from agentops.repository import Repository
from agentops.schemas import (
    AgentResponse,
    ConversationCreate,
    ConversationRead,
    MessageCreate,
    MetricsSummary,
    RunRead,
    TenantRead,
)

router = APIRouter()
Session = Annotated[AsyncSession, Depends(get_session)]


async def current_tenant_id(
    session: Session,
    x_tenant_id: Annotated[str, Header()] = "tenant_northstar",
) -> str:
    if await Repository(session).get_tenant(x_tenant_id) is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return x_tenant_id


TenantId = Annotated[str, Depends(current_tenant_id)]


@router.get("/health", tags=["system"])
async def health(session: Session) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "healthy", "service": "agentops-studio-api"}


@router.get("/api/v1/tenants", response_model=list[TenantRead], tags=["tenants"])
async def list_tenants(session: Session) -> list[TenantRead]:
    return list(await Repository(session).list_tenants())


@router.post(
    "/api/v1/conversations",
    response_model=ConversationRead,
    status_code=status.HTTP_201_CREATED,
    tags=["conversations"],
)
async def create_conversation(
    payload: ConversationCreate, session: Session, tenant_id: TenantId
) -> ConversationRead:
    return await Repository(session).create_conversation(tenant_id, payload.title)


@router.get(
    "/api/v1/conversations", response_model=list[ConversationRead], tags=["conversations"]
)
async def list_conversations(session: Session, tenant_id: TenantId) -> list[ConversationRead]:
    return list(await Repository(session).list_conversations(tenant_id))


@router.post(
    "/api/v1/conversations/{conversation_id}/messages",
    response_model=AgentResponse,
    tags=["agent"],
)
async def create_message(
    conversation_id: str,
    payload: MessageCreate,
    request: Request,
    session: Session,
    tenant_id: TenantId,
) -> AgentResponse:
    repository = Repository(session)
    conversation = await repository.get_conversation(conversation_id, tenant_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    orchestrator = AgentOrchestrator(
        session,
        request.app.state.settings,
        request.app.state.provider,
        request.app.state.tools,
    )
    run = await orchestrator.run(conversation, tenant_id, payload.content)
    return AgentResponse(conversation_id=conversation_id, run=RunRead.model_validate(run))


@router.get("/api/v1/runs", response_model=list[RunRead], tags=["runs"])
async def list_runs(
    session: Session,
    tenant_id: TenantId,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[RunRead]:
    return list(await Repository(session).list_runs(tenant_id, limit))


@router.get("/api/v1/runs/{run_id}", response_model=RunRead, tags=["runs"])
async def get_run(run_id: str, session: Session, tenant_id: TenantId) -> RunRead:
    run = await Repository(session).get_run(run_id, tenant_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunRead.model_validate(run)


@router.get("/api/v1/tools", tags=["tools"])
async def list_tools(request: Request, tenant_id: TenantId) -> dict:
    return {"tenant_id": tenant_id, "tools": request.app.state.tools.schemas()}


@router.get("/api/v1/metrics/summary", response_model=MetricsSummary, tags=["metrics"])
async def metrics_summary(
    session: Session,
    tenant_id: TenantId,
    days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> MetricsSummary:
    return await Repository(session).metrics(tenant_id, days)
