from __future__ import annotations

import pytest

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
async def test_registry_executes_a_tenant_scoped_tool() -> None:
    registry = ToolRegistry(timeout_seconds=1, retry_attempts=0)
    execution = await registry.execute(
        "search_orders",
        {"status": "at_risk", "minimum_value_usd": 2500, "limit": 5},
        "tenant_northstar",
    )
    assert execution.output["tenant_id"] == "tenant_northstar"
    assert execution.output["count"] == 2
    assert execution.attempts == 1


# Ensures malformed model arguments are rejected at the registry boundary with a typed error.
async def test_registry_rejects_unknown_arguments() -> None:
    registry = ToolRegistry(timeout_seconds=1, retry_attempts=0)
    with pytest.raises(ToolError, match="extra_forbidden") as error:
        await registry.execute(
            "get_customer_health",
            {"customer_id": "CUS-2041", "unsafe_override": True},
            "tenant_northstar",
        )
    assert error.value.code == "tool_validation_error"
