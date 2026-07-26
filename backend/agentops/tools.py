from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from time import perf_counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agentops.models import (
    CommerceOrder,
    CustomerHealthRecord,
    InventoryRecord,
    KnowledgeRecord,
    RevenueSummaryRecord,
)


class StrictToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RevenueSummaryInput(StrictToolInput):
    start_date: date
    end_date: date
    channel: Literal["all", "web", "marketplace", "retail"]


class SearchOrdersInput(StrictToolInput):
    status: Literal["all", "pending", "paid", "refunded", "at_risk"]
    minimum_value_usd: float = Field(ge=0)
    limit: int = Field(ge=1, le=25)


class CustomerHealthInput(StrictToolInput):
    customer_id: str = Field(min_length=1, max_length=80)


class KnowledgeSearchInput(StrictToolInput):
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(ge=1, le=8)


class InventoryAlertsInput(StrictToolInput):
    warehouse: Literal["all", "east", "west", "central"]
    days_of_cover_below: int = Field(ge=1, le=30)


ToolHandler = Callable[
    [AsyncSession, str, StrictToolInput], Awaitable[dict[str, Any]]
]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[StrictToolInput]
    handler: ToolHandler

    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.input_model.model_json_schema(),
            "strict": True,
        }


@dataclass(frozen=True)
class ToolExecution:
    output: dict[str, Any]
    duration_ms: int
    attempts: int


class ToolError(Exception):
    def __init__(
        self, code: str, message: str, *, retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


async def get_revenue_summary(
    session: AsyncSession, tenant_id: str, payload: StrictToolInput
) -> dict[str, Any]:
    request = RevenueSummaryInput.model_validate(payload)
    record = await session.scalar(
        select(RevenueSummaryRecord).where(
            RevenueSummaryRecord.tenant_id == tenant_id,
            RevenueSummaryRecord.start_date == request.start_date,
            RevenueSummaryRecord.end_date == request.end_date,
            RevenueSummaryRecord.channel == request.channel,
        )
    )
    if record is None:
        raise ToolError(
            "data_not_found",
            "No revenue summary matched the requested tenant, period, and channel.",
        )
    return {
        "source": "postgresql.revenue_summaries",
        "period": {
            "start": record.start_date.isoformat(),
            "end": record.end_date.isoformat(),
        },
        "channel": record.channel,
        "currency": record.currency,
        "gross_revenue": float(record.gross_revenue),
        "net_revenue": float(record.net_revenue),
        "orders": record.orders,
        "refund_rate": float(record.refund_rate),
        "change_vs_previous_period_pct": float(
            record.change_vs_previous_period_pct
        ),
    }


async def search_orders(
    session: AsyncSession, tenant_id: str, payload: StrictToolInput
) -> dict[str, Any]:
    request = SearchOrdersInput.model_validate(payload)
    query = (
        select(CommerceOrder)
        .where(
            CommerceOrder.tenant_id == tenant_id,
            CommerceOrder.value_usd >= request.minimum_value_usd,
        )
        .order_by(CommerceOrder.value_usd.desc())
        .limit(request.limit)
    )
    if request.status != "all":
        query = query.where(CommerceOrder.status == request.status)
    records = list((await session.scalars(query)).all())
    return {
        "source": "postgresql.commerce_orders",
        "tenant_id": tenant_id,
        "count": len(records),
        "orders": [
            {
                "order_id": record.order_id,
                "customer_id": record.customer_id,
                "customer": record.customer,
                "status": record.status,
                "value_usd": float(record.value_usd),
                "risk": record.risk,
            }
            for record in records
        ],
        "filters": request.model_dump(mode="json"),
    }


async def get_customer_health(
    session: AsyncSession, tenant_id: str, payload: StrictToolInput
) -> dict[str, Any]:
    request = CustomerHealthInput.model_validate(payload)
    record = await session.scalar(
        select(CustomerHealthRecord).where(
            CustomerHealthRecord.tenant_id == tenant_id,
            CustomerHealthRecord.customer_id == request.customer_id,
        )
    )
    if record is None:
        raise ToolError(
            "data_not_found",
            f"No customer health record found for {request.customer_id}.",
        )
    return {
        "source": "postgresql.customer_health",
        "tenant_id": tenant_id,
        "customer_id": record.customer_id,
        "name": record.name,
        "health_score": record.health_score,
        "segment": record.segment,
        "lifetime_value_usd": float(record.lifetime_value_usd),
        "open_support_cases": record.open_support_cases,
        "recommended_action": record.recommended_action,
    }


async def search_knowledge(
    session: AsyncSession, tenant_id: str, payload: StrictToolInput
) -> dict[str, Any]:
    request = KnowledgeSearchInput.model_validate(payload)
    pattern = f"%{request.query}%"
    query = (
        select(KnowledgeRecord)
        .where(
            KnowledgeRecord.tenant_id == tenant_id,
            or_(
                KnowledgeRecord.title.ilike(pattern),
                KnowledgeRecord.excerpt.ilike(pattern),
            ),
        )
        .order_by(KnowledgeRecord.score.desc())
        .limit(request.limit)
    )
    records = list((await session.scalars(query)).all())
    if not records:
        records = list(
            (
                await session.scalars(
                    select(KnowledgeRecord)
                    .where(KnowledgeRecord.tenant_id == tenant_id)
                    .order_by(KnowledgeRecord.score.desc())
                    .limit(request.limit)
                )
            ).all()
        )
    return {
        "source": "postgresql.knowledge_records",
        "tenant_id": tenant_id,
        "query": request.query,
        "matches": [
            {
                "title": record.title,
                "section": record.section,
                "excerpt": record.excerpt,
                "score": float(record.score),
            }
            for record in records
        ],
    }


async def get_inventory_alerts(
    session: AsyncSession, tenant_id: str, payload: StrictToolInput
) -> dict[str, Any]:
    request = InventoryAlertsInput.model_validate(payload)
    query = (
        select(InventoryRecord)
        .where(
            InventoryRecord.tenant_id == tenant_id,
            InventoryRecord.days_of_cover < request.days_of_cover_below,
        )
        .order_by(InventoryRecord.days_of_cover)
    )
    if request.warehouse != "all":
        query = query.where(InventoryRecord.warehouse == request.warehouse)
    records = list((await session.scalars(query)).all())
    return {
        "source": "postgresql.inventory_records",
        "tenant_id": tenant_id,
        "warehouse": request.warehouse,
        "threshold_days": request.days_of_cover_below,
        "items": [
            {
                "warehouse": record.warehouse,
                "sku": record.sku,
                "name": record.name,
                "days_of_cover": float(record.days_of_cover),
            }
            for record in records
        ],
    }


class ToolRegistry:
    def __init__(self, timeout_seconds: float, retry_attempts: int) -> None:
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts
        definitions = [
            ToolDefinition(
                "get_revenue_summary",
                "Query PostgreSQL for revenue, order volume and refund metrics by period.",
                RevenueSummaryInput,
                get_revenue_summary,
            ),
            ToolDefinition(
                "search_orders",
                "Query PostgreSQL for orders by status and minimum value, including risk signals.",
                SearchOrdersInput,
                search_orders,
            ),
            ToolDefinition(
                "get_customer_health",
                "Query PostgreSQL for customer health, lifetime value, "
                "support load and next action.",
                CustomerHealthInput,
                get_customer_health,
            ),
            ToolDefinition(
                "search_knowledge",
                "Search tenant operating procedures stored in PostgreSQL.",
                KnowledgeSearchInput,
                search_knowledge,
            ),
            ToolDefinition(
                "get_inventory_alerts",
                "Query PostgreSQL for inventory below a days-of-cover threshold.",
                InventoryAlertsInput,
                get_inventory_alerts,
            ),
        ]
        self._definitions = {
            definition.name: definition for definition in definitions
        }

    def schemas(self) -> list[dict[str, Any]]:
        return [
            definition.openai_schema()
            for definition in self._definitions.values()
        ]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        tenant_id: str,
        session: AsyncSession,
    ) -> ToolExecution:
        definition = self._definitions.get(name)
        if definition is None:
            raise ToolError("tool_not_found", f"Unknown tool: {name}")
        try:
            payload = definition.input_model.model_validate(arguments)
        except ValidationError as exc:
            raise ToolError("tool_validation_error", str(exc)) from exc

        started = perf_counter()
        attempts = 0
        while True:
            attempts += 1
            cause: Exception
            try:
                output = await asyncio.wait_for(
                    definition.handler(session, tenant_id, payload),
                    timeout=self.timeout_seconds,
                )
                return ToolExecution(
                    output=output,
                    duration_ms=round((perf_counter() - started) * 1000),
                    attempts=attempts,
                )
            except TimeoutError as exc:
                cause = exc
                error = ToolError(
                    "tool_timeout", f"{name} timed out", retryable=True
                )
            except ToolError as exc:
                cause = exc
                error = exc
            except Exception as exc:
                cause = exc
                error = ToolError(
                    "tool_execution_error", str(exc), retryable=True
                )

            if not error.retryable or attempts > self.retry_attempts:
                raise error from cause
            await asyncio.sleep(0.05 * attempts)
