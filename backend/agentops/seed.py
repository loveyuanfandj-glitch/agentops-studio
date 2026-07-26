from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agentops.models import AgentRun, Conversation, RunStep, Tenant


async def seed_demo_data(session: AsyncSession) -> None:
    existing = await session.scalar(select(Tenant.id).limit(1))
    if existing:
        return

    tenants = [
        Tenant(
            id="tenant_northstar",
            name="Northstar Retail",
            slug="northstar-retail",
            plan="scale",
            monthly_budget_usd=Decimal("250"),
        ),
        Tenant(
            id="tenant_luma",
            name="Luma Commerce",
            slug="luma-commerce",
            plan="growth",
            monthly_budget_usd=Decimal("125"),
        ),
        Tenant(
            id="tenant_atlas",
            name="Atlas Supply",
            slug="atlas-supply",
            plan="growth",
            monthly_budget_usd=Decimal("90"),
        ),
    ]
    session.add_all(tenants)
    conversation = Conversation(
        id="conv_demo_revenue",
        tenant_id="tenant_northstar",
        title="Revenue risk review",
    )
    session.add(conversation)
    await session.flush()

    now = datetime.now(UTC)
    for index, status in enumerate(
        ["succeeded", "succeeded", "succeeded", "guarded", "succeeded", "failed", "succeeded"]
    ):
        started = now - timedelta(days=6 - index, hours=index)
        run = AgentRun(
            id=f"run_seed_{index + 1:02d}",
            tenant_id="tenant_northstar",
            conversation_id=conversation.id,
            status=status,
            model="gpt-5.6-terra",
            prompt="Review operational risk and recommend the next best action.",
            answer="Seeded operational review for dashboard metrics.",
            error_code="provider_request_failed" if status == "failed" else None,
            guardrail_reason="maximum model steps reached" if status == "guarded" else None,
            steps_count=3,
            input_tokens=1_820 + index * 94,
            output_tokens=210 + index * 13,
            cached_tokens=340 + index * 20,
            cost_usd=Decimal("0.0094") + Decimal(index) * Decimal("0.0011"),
            latency_ms=980 + index * 118,
            started_at=started,
            completed_at=started + timedelta(milliseconds=980 + index * 118),
        )
        run.steps.append(
            RunStep(
                sequence=1,
                kind="model",
                name="gpt-5.6-terra",
                status="completed",
                duration_ms=410,
                output={"tool_calls": ["get_revenue_summary"]},
            )
        )
        run.steps.append(
            RunStep(
                sequence=2,
                kind="tool",
                name="get_revenue_summary",
                status="completed",
                arguments={
                    "start_date": "2026-07-01",
                    "end_date": "2026-07-26",
                    "channel": "all",
                },
                output={"gross_revenue": 184620.42, "change_vs_previous_period_pct": 12.4},
                duration_ms=12,
            )
        )
        run.steps.append(
            RunStep(
                sequence=3,
                kind="model",
                name="gpt-5.6-terra",
                status="completed",
                duration_ms=558,
                output={"tool_calls": [], "has_final_answer": True},
            )
        )
        session.add(run)
    await session.commit()
