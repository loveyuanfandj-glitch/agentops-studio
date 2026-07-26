from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agentops.api import router
from agentops.config import Settings
from agentops.database import get_session
from agentops.providers import MockProvider
from agentops.tools import ToolRegistry


# Validates the public API from conversation creation through a persisted multi-tool agent response.
async def test_agent_api_flow(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    app = FastAPI()
    app.include_router(router)
    app.state.settings = Settings(app_env="test")
    app.state.provider = MockProvider()
    app.state.tools = ToolRegistry(timeout_seconds=1, retry_attempts=0)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        conversation_response = await client.post(
            "/api/v1/conversations", json={"title": "Revenue investigation"}
        )
        conversation_id = conversation_response.json()["id"]
        run_response = await client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "Review revenue risk."},
        )

    assert conversation_response.status_code == 201
    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["run"]["status"] == "succeeded"
    assert payload["run"]["steps_count"] == 7
    assert payload["run"]["cost_usd"] == "0.01424000"


# Confirms tenant isolation by rejecting access to a conversation through an unknown tenant header.
async def test_api_rejects_unknown_tenant(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    app = FastAPI()
    app.include_router(router)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/conversations", headers={"X-Tenant-ID": "tenant_unknown"}
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"
