from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agentops.models import AgentRun, Conversation, Message, Tenant
from agentops.schemas import MetricPoint, MetricsSummary


class Repository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_tenants(self) -> list[Tenant]:
        result = await self.session.scalars(select(Tenant).order_by(Tenant.name))
        return list(result)

    async def get_tenant(self, tenant_id: str) -> Tenant | None:
        return await self.session.get(Tenant, tenant_id)

    async def create_conversation(self, tenant_id: str, title: str) -> Conversation:
        conversation = Conversation(tenant_id=tenant_id, title=title)
        self.session.add(conversation)
        await self.session.commit()
        await self.session.refresh(conversation, attribute_names=["messages"])
        return conversation

    async def list_conversations(self, tenant_id: str) -> list[Conversation]:
        query = (
            select(Conversation)
            .where(Conversation.tenant_id == tenant_id)
            .options(selectinload(Conversation.messages))
            .order_by(Conversation.updated_at.desc())
        )
        return list(await self.session.scalars(query))

    async def get_conversation(
        self, conversation_id: str, tenant_id: str
    ) -> Conversation | None:
        query = (
            select(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.tenant_id == tenant_id,
            )
            .options(selectinload(Conversation.messages))
        )
        return await self.session.scalar(query)

    async def list_runs(self, tenant_id: str, limit: int = 50) -> list[AgentRun]:
        query = (
            select(AgentRun)
            .where(AgentRun.tenant_id == tenant_id)
            .options(selectinload(AgentRun.steps))
            .order_by(AgentRun.started_at.desc())
            .limit(limit)
        )
        return list(await self.session.scalars(query))

    async def get_run(self, run_id: str, tenant_id: str) -> AgentRun | None:
        query = (
            select(AgentRun)
            .where(AgentRun.id == run_id, AgentRun.tenant_id == tenant_id)
            .options(selectinload(AgentRun.steps))
        )
        return await self.session.scalar(query)

    async def metrics(self, tenant_id: str, days: int) -> MetricsSummary:
        since = datetime.now(UTC) - timedelta(days=days)
        query = select(AgentRun).where(
            AgentRun.tenant_id == tenant_id, AgentRun.started_at >= since
        )
        runs = list(await self.session.scalars(query))
        successful = sum(run.status == "succeeded" for run in runs)
        guarded = sum(run.status == "guarded" for run in runs)
        failed = sum(run.status == "failed" for run in runs)
        buckets: dict[str, dict[str, int | Decimal]] = {}
        for run in runs:
            bucket = run.started_at.date().isoformat()
            point = buckets.setdefault(
                bucket,
                {"runs": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": Decimal(0)},
            )
            point["runs"] += 1
            point["input_tokens"] += run.input_tokens
            point["output_tokens"] += run.output_tokens
            point["cost_usd"] += run.cost_usd

        timeseries = [
            MetricPoint(bucket=bucket, **values)
            for bucket, values in sorted(buckets.items())
        ]
        total = len(runs)
        latencies = [run.latency_ms for run in runs if run.latency_ms is not None]
        return MetricsSummary(
            total_runs=total,
            successful_runs=successful,
            guarded_runs=guarded,
            failed_runs=failed,
            success_rate=round(successful / total * 100, 2) if total else 0,
            input_tokens=sum(run.input_tokens for run in runs),
            output_tokens=sum(run.output_tokens for run in runs),
            cached_tokens=sum(run.cached_tokens for run in runs),
            cost_usd=sum((run.cost_usd for run in runs), start=Decimal(0)),
            average_latency_ms=round(sum(latencies) / len(latencies), 2) if latencies else 0,
            timeseries=timeseries,
        )

    async def add_message(self, conversation_id: str, role: str, content: str) -> Message:
        message = Message(conversation_id=conversation_id, role=role, content=content)
        self.session.add(message)
        return message
