from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agentops.tools import ToolError, ToolRegistry


# Validates strict schema generation and the prohibition of undeclared tool arguments.
def test_tool_schemas_are_strict() -> None:
    registry = ToolRegistry(timeout_seconds=1, retry_attempts=0)
    for schema in registry.schemas():
        parameters = schema["parameters"]
        assert schema["strict"] is True
        assert parameters["additionalProperties"] is False
        assert set(parameters["required"]) == set(parameters["properties"])


# Covers a successful tenant-scoped tool execution and its structured result metadata.
async def test_registry_executes_a_tenant_scoped_tool(
    session: AsyncSession,
) -> None:
    registry = ToolRegistry(timeout_seconds=1, retry_attempts=0)
    execution = await registry.execute(
        "search_orders",
        {"status": "at_risk", "minimum_value_usd": 2500, "limit": 5},
        "tenant_northstar",
        session,
    )
    assert execution.output["tenant_id"] == "tenant_northstar"
    assert execution.output["count"] == 2
    assert execution.attempts == 1


# Ensures malformed model arguments are rejected at the registry boundary with a typed error.
async def test_registry_rejects_unknown_arguments(
    session: AsyncSession,
) -> None:
    registry = ToolRegistry(timeout_seconds=1, retry_attempts=0)
    with pytest.raises(ToolError, match="extra_forbidden") as error:
        await registry.execute(
            "get_customer_health",
            {"customer_id": "CUS-2041", "unsafe_override": True},
            "tenant_northstar",
            session,
        )
    assert error.value.code == "tool_validation_error"


# Exercises the PostgreSQL-style knowledge and inventory query paths, including
# tenant-scoped filtering, relevance fallback, thresholds, and structured sources.
async def test_registry_queries_remaining_operational_tools(
    session: AsyncSession,
) -> None:
    registry = ToolRegistry(timeout_seconds=1, retry_attempts=0)

    knowledge = await registry.execute(
        "search_knowledge",
        {"query": "at-risk order playbook", "limit": 2},
        "tenant_northstar",
        session,
    )
    inventory = await registry.execute(
        "get_inventory_alerts",
        {"warehouse": "all", "days_of_cover_below": 5},
        "tenant_northstar",
        session,
    )

    assert knowledge.output["source"] == "postgresql.knowledge_records"
    assert knowledge.output["matches"][0]["title"] == "At-risk order playbook"
    assert inventory.output["source"] == "postgresql.inventory_records"
    assert {item["sku"] for item in inventory.output["items"]} == {
        "NS-AX14",
        "NS-BT07",
    }


# Confirms valid requests with no matching tenant data return typed, non-retryable
# tool failures rather than fabricated customer or revenue records.
async def test_registry_rejects_missing_operational_data(
    session: AsyncSession,
) -> None:
    registry = ToolRegistry(timeout_seconds=1, retry_attempts=0)

    with pytest.raises(ToolError) as revenue_error:
        await registry.execute(
            "get_revenue_summary",
            {
                "start_date": "2026-06-01",
                "end_date": "2026-06-30",
                "channel": "all",
            },
            "tenant_northstar",
            session,
        )
    with pytest.raises(ToolError) as customer_error:
        await registry.execute(
            "get_customer_health",
            {"customer_id": "CUS-MISSING"},
            "tenant_northstar",
            session,
        )

    assert revenue_error.value.code == "data_not_found"
    assert customer_error.value.code == "data_not_found"
