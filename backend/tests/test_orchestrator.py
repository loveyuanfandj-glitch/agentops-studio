from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from agentops.config import Settings
from agentops.models import Conversation
from agentops.orchestrator import AgentOrchestrator
from agentops.providers import MockProvider, ProviderTurn, TokenUsage, ToolCall
from agentops.tools import ToolRegistry


class RepeatingProvider:
    async def respond(self, input_items: list[dict], tools: list[dict], instructions: str):
        del input_items, tools, instructions
        arguments = {"customer_id": "CUS-2041"}
        return ProviderTurn(
            output_items=[
                {
                    "type": "function_call",
                    "call_id": "repeat_call",
                    "name": "get_customer_health",
                    "arguments": '{"customer_id":"CUS-2041"}',
                }
            ],
            tool_calls=[ToolCall("repeat_call", "get_customer_health", arguments)],
            usage=TokenUsage(input_tokens=50, output_tokens=10),
        )


# Exercises the complete model-tool loop, sequential dependencies, persistence, and cost tracking.
async def test_orchestrator_completes_a_multi_step_run(session: AsyncSession) -> None:
    conversation = Conversation(
        tenant_id="tenant_northstar", title="Revenue review", messages=[]
    )
    session.add(conversation)
    await session.commit()
    orchestrator = AgentOrchestrator(
        session,
        Settings(app_env="test"),
        MockProvider(),
        ToolRegistry(timeout_seconds=1, retry_attempts=0),
    )

    run = await orchestrator.run(
        conversation,
        "tenant_northstar",
        "Review revenue risk and identify customers needing attention.",
    )

    assert run.status == "succeeded"
    assert [step.name for step in run.steps if step.kind == "tool"] == [
        "get_revenue_summary",
        "search_orders",
        "get_customer_health",
    ]
    assert run.steps_count == 7
    assert run.input_tokens == 4010
    assert run.cost_usd > 0
    assert "ORD-10482" in run.answer


# Verifies that identical tool signatures are stopped before an agent can loop indefinitely.
async def test_orchestrator_guards_repeated_tool_calls(session: AsyncSession) -> None:
    conversation = Conversation(
        tenant_id="tenant_northstar", title="Loop guard", messages=[]
    )
    session.add(conversation)
    await session.commit()
    settings = Settings(app_env="test", max_repeated_tool_calls=1, max_agent_steps=4)
    orchestrator = AgentOrchestrator(
        session,
        settings,
        RepeatingProvider(),
        ToolRegistry(timeout_seconds=1, retry_attempts=0),
    )

    run = await orchestrator.run(conversation, "tenant_northstar", "Keep checking health.")

    assert run.status == "guarded"
    assert run.guardrail_reason == "repeated tool call detected for get_customer_health"
    assert run.steps_count == 3
