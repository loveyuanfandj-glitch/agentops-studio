from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class StrictToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RevenueSummaryInput(StrictToolInput):
    start_date: str
    end_date: str
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


ToolHandler = Callable[[str, StrictToolInput], Awaitable[dict[str, Any]]]


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
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


async def get_revenue_summary(
    tenant_id: str, payload: StrictToolInput
) -> dict[str, Any]:
    request = RevenueSummaryInput.model_validate(payload)
    tenant_multiplier = 1.0 if tenant_id == "tenant_northstar" else 0.72
    gross = round(184_620.42 * tenant_multiplier, 2)
    return {
        "period": {"start": request.start_date, "end": request.end_date},
        "channel": request.channel,
        "currency": "USD",
        "gross_revenue": gross,
        "net_revenue": round(gross * 0.921, 2),
        "orders": round(1_428 * tenant_multiplier),
        "refund_rate": 0.028,
        "change_vs_previous_period_pct": 12.4,
    }


async def search_orders(tenant_id: str, payload: StrictToolInput) -> dict[str, Any]:
    request = SearchOrdersInput.model_validate(payload)
    orders = [
        {
            "order_id": "ORD-10482",
            "customer_id": "CUS-2041",
            "customer": "Avery Stone",
            "status": "at_risk",
            "value_usd": 4_820.0,
            "risk": "Payment retry failed twice",
        },
        {
            "order_id": "ORD-10471",
            "customer_id": "CUS-1188",
            "customer": "Morgan Labs",
            "status": "at_risk",
            "value_usd": 3_680.0,
            "risk": "Fulfilment SLA exceeded",
        },
        {
            "order_id": "ORD-10466",
            "customer_id": "CUS-1410",
            "customer": "Northwind Goods",
            "status": "paid",
            "value_usd": 2_940.0,
            "risk": None,
        },
    ]
    filtered = [
        order
        for order in orders
        if (request.status == "all" or order["status"] == request.status)
        and order["value_usd"] >= request.minimum_value_usd
    ][: request.limit]
    return {
        "tenant_id": tenant_id,
        "count": len(filtered),
        "orders": filtered,
        "filters": request.model_dump(),
    }


async def get_customer_health(
    tenant_id: str, payload: StrictToolInput
) -> dict[str, Any]:
    request = CustomerHealthInput.model_validate(payload)
    customers = {
        "CUS-2041": {
            "name": "Avery Stone",
            "health_score": 46,
            "segment": "enterprise",
            "lifetime_value_usd": 38_440,
            "open_support_cases": 2,
            "recommended_action": "Assign account owner and resolve payment method today",
        },
        "CUS-1188": {
            "name": "Morgan Labs",
            "health_score": 62,
            "segment": "growth",
            "lifetime_value_usd": 21_880,
            "open_support_cases": 1,
            "recommended_action": "Expedite shipment and issue proactive delivery update",
        },
    }
    return {
        "tenant_id": tenant_id,
        "customer_id": request.customer_id,
        **customers.get(
            request.customer_id,
            {
                "name": "Unknown customer",
                "health_score": 75,
                "segment": "standard",
                "lifetime_value_usd": 0,
                "open_support_cases": 0,
                "recommended_action": "No immediate action",
            },
        ),
    }


async def search_knowledge(tenant_id: str, payload: StrictToolInput) -> dict[str, Any]:
    request = KnowledgeSearchInput.model_validate(payload)
    matches = [
        {
            "title": "At-risk order playbook",
            "section": "Revenue operations",
            "excerpt": "Prioritize failed payments above $2,500 and contact the account owner.",
            "score": 0.93,
        },
        {
            "title": "Fulfilment incident policy",
            "section": "Customer experience",
            "excerpt": "Send a proactive update when the fulfilment SLA exceeds four hours.",
            "score": 0.86,
        },
    ][: request.limit]
    return {"tenant_id": tenant_id, "query": request.query, "matches": matches}


async def get_inventory_alerts(
    tenant_id: str, payload: StrictToolInput
) -> dict[str, Any]:
    request = InventoryAlertsInput.model_validate(payload)
    return {
        "tenant_id": tenant_id,
        "warehouse": request.warehouse,
        "threshold_days": request.days_of_cover_below,
        "items": [
            {"sku": "NS-AX14", "name": "Arc Desk Lamp", "days_of_cover": 3.2},
            {"sku": "NS-BT07", "name": "Balance Tray", "days_of_cover": 4.7},
        ],
    }


class ToolRegistry:
    def __init__(self, timeout_seconds: float, retry_attempts: int) -> None:
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts
        definitions = [
            ToolDefinition(
                "get_revenue_summary",
                "Return revenue, order volume and refund metrics for a date range and channel.",
                RevenueSummaryInput,
                get_revenue_summary,
            ),
            ToolDefinition(
                "search_orders",
                "Find orders by status and minimum value, including operational risk signals.",
                SearchOrdersInput,
                search_orders,
            ),
            ToolDefinition(
                "get_customer_health",
                "Return customer health, lifetime value, support load and the next best action.",
                CustomerHealthInput,
                get_customer_health,
            ),
            ToolDefinition(
                "search_knowledge",
                "Search internal operating procedures and return grounded policy excerpts.",
                KnowledgeSearchInput,
                search_knowledge,
            ),
            ToolDefinition(
                "get_inventory_alerts",
                "List inventory items whose projected days of cover fall below a threshold.",
                InventoryAlertsInput,
                get_inventory_alerts,
            ),
        ]
        self._definitions = {definition.name: definition for definition in definitions}

    def schemas(self) -> list[dict[str, Any]]:
        return [definition.openai_schema() for definition in self._definitions.values()]

    async def execute(
        self, name: str, arguments: dict[str, Any], tenant_id: str
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
                    definition.handler(tenant_id, payload), timeout=self.timeout_seconds
                )
                return ToolExecution(
                    output=output,
                    duration_ms=round((perf_counter() - started) * 1000),
                    attempts=attempts,
                )
            except TimeoutError as exc:
                cause = exc
                error = ToolError("tool_timeout", f"{name} timed out", retryable=True)
            except ToolError as exc:
                cause = exc
                error = exc
            except Exception as exc:  # External integrations are normalized at this boundary.
                cause = exc
                error = ToolError("tool_execution_error", str(exc), retryable=True)

            if not error.retryable or attempts > self.retry_attempts:
                raise error from cause
            await asyncio.sleep(0.05 * attempts)
