from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agentops.models import (
    AgentRun,
    CommerceOrder,
    Conversation,
    CustomerHealthRecord,
    InventoryRecord,
    KnowledgeRecord,
    RevenueSummaryRecord,
    RunStep,
    Tenant,
)


async def seed_operational_data(session: AsyncSession) -> None:
    existing = await session.scalar(select(RevenueSummaryRecord.id).limit(1))
    if existing:
        return

    session.add(
        RevenueSummaryRecord(
            tenant_id="tenant_northstar",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 26),
            channel="all",
            currency="USD",
            gross_revenue=Decimal("184620.42"),
            net_revenue=Decimal("170035.41"),
            orders=1428,
            refund_rate=Decimal("0.028"),
            change_vs_previous_period_pct=Decimal("12.4"),
        )
    )
    session.add_all(
        [
            CommerceOrder(
                tenant_id="tenant_northstar",
                order_id="ORD-10482",
                customer_id="CUS-2041",
                customer="Avery Stone",
                status="at_risk",
                value_usd=Decimal("4820"),
                risk="Payment retry failed twice",
            ),
            CommerceOrder(
                tenant_id="tenant_northstar",
                order_id="ORD-10471",
                customer_id="CUS-1188",
                customer="Morgan Labs",
                status="at_risk",
                value_usd=Decimal("3680"),
                risk="Fulfilment SLA exceeded",
            ),
            CommerceOrder(
                tenant_id="tenant_northstar",
                order_id="ORD-10466",
                customer_id="CUS-1410",
                customer="Northwind Goods",
                status="paid",
                value_usd=Decimal("2940"),
                risk=None,
            ),
        ]
    )
    session.add_all(
        [
            CustomerHealthRecord(
                tenant_id="tenant_northstar",
                customer_id="CUS-2041",
                name="Avery Stone",
                health_score=46,
                segment="enterprise",
                lifetime_value_usd=Decimal("38440"),
                open_support_cases=2,
                recommended_action=(
                    "Assign account owner and resolve payment method today"
                ),
            ),
            CustomerHealthRecord(
                tenant_id="tenant_northstar",
                customer_id="CUS-1188",
                name="Morgan Labs",
                health_score=62,
                segment="growth",
                lifetime_value_usd=Decimal("21880"),
                open_support_cases=1,
                recommended_action=(
                    "Expedite shipment and issue proactive delivery update"
                ),
            ),
        ]
    )
    session.add_all(
        [
            KnowledgeRecord(
                tenant_id="tenant_northstar",
                title="At-risk order playbook",
                section="Revenue operations",
                excerpt=(
                    "Prioritize failed payments above $2,500 and contact the "
                    "account owner."
                ),
                score=Decimal("0.93"),
            ),
            KnowledgeRecord(
                tenant_id="tenant_northstar",
                title="Fulfilment incident policy",
                section="Customer experience",
                excerpt=(
                    "Send a proactive update when the fulfilment SLA exceeds "
                    "four hours."
                ),
                score=Decimal("0.86"),
            ),
        ]
    )
    session.add_all(
        [
            InventoryRecord(
                tenant_id="tenant_northstar",
                warehouse="east",
                sku="NS-AX14",
                name="Arc Desk Lamp",
                days_of_cover=Decimal("3.2"),
            ),
            InventoryRecord(
                tenant_id="tenant_northstar",
                warehouse="west",
                sku="NS-BT07",
                name="Balance Tray",
                days_of_cover=Decimal("4.7"),
            ),
        ]
    )


async def seed_demo_data(session: AsyncSession) -> None:
    existing = await session.scalar(select(Tenant.id).limit(1))
    if not existing:
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
        statuses = [
            "succeeded",
            "succeeded",
            "succeeded",
            "guarded",
            "succeeded",
            "failed",
            "succeeded",
        ]
        for index, status in enumerate(statuses):
            started = now - timedelta(days=6 - index, hours=index)
            run = AgentRun(
                id=f"run_seed_{index + 1:02d}",
                tenant_id="tenant_northstar",
                conversation_id=conversation.id,
                status=status,
                model="deterministic-demo",
                prompt="Review operational risk and recommend the next best action.",
                answer="Seeded operational review for dashboard metrics.",
                error_code=(
                    "provider_request_failed" if status == "failed" else None
                ),
                guardrail_reason=(
                    "maximum model steps reached" if status == "guarded" else None
                ),
                steps_count=3,
                input_tokens=1_820 + index * 94,
                output_tokens=210 + index * 13,
                cached_tokens=340 + index * 20,
                cost_usd=Decimal("0.0094")
                + Decimal(index) * Decimal("0.0011"),
                latency_ms=980 + index * 118,
                started_at=started,
                completed_at=started
                + timedelta(milliseconds=980 + index * 118),
            )
            run.steps.append(
                RunStep(
                    sequence=1,
                    kind="model",
                    name="deterministic-demo",
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
                    output={
                        "gross_revenue": 184620.42,
                        "change_vs_previous_period_pct": 12.4,
                    },
                    duration_ms=12,
                )
            )
            run.steps.append(
                RunStep(
                    sequence=3,
                    kind="model",
                    name="deterministic-demo",
                    status="completed",
                    duration_ms=558,
                    output={"tool_calls": [], "has_final_answer": True},
                )
            )
            session.add(run)

    await seed_operational_data(session)
    await session.commit()
