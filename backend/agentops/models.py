from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from agentops.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


def prefixed_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(40), default="growth", nullable=False)
    monthly_budget_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=75)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    conversations: Mapped[list[Conversation]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    runs: Mapped[list[AgentRun]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: prefixed_id("conv")
    )
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    tenant: Mapped[Tenant] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )
    runs: Mapped[list[AgentRun]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: prefixed_id("msg")
    )
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_tenant_started", "tenant_id", "started_at"),
        Index("ix_agent_runs_status_started", "status", "started_at"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: prefixed_id("run")
    )
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(80))
    guardrail_reason: Mapped[str | None] = mapped_column(String(240))
    steps_count: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(14, 8), default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped[Tenant] = relationship(back_populates="runs")
    conversation: Mapped[Conversation] = relationship(back_populates="runs")
    steps: Mapped[list[RunStep]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="RunStep.sequence"
    )


class RunStep(Base):
    __tablename__ = "run_steps"
    __table_args__ = (Index("ix_run_steps_run_sequence", "run_id", "sequence", unique=True),)

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: prefixed_id("step")
    )
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    arguments: Mapped[dict | None] = mapped_column(JSON_TYPE)
    output: Mapped[dict | None] = mapped_column(JSON_TYPE)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    run: Mapped[AgentRun] = relationship(back_populates="steps")


class RevenueSummaryRecord(Base):
    __tablename__ = "revenue_summaries"
    __table_args__ = (
        Index(
            "ix_revenue_summaries_lookup",
            "tenant_id",
            "start_date",
            "end_date",
            "channel",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: prefixed_id("rev")
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    gross_revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    net_revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    orders: Mapped[int] = mapped_column(Integer, nullable=False)
    refund_rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    change_vs_previous_period_pct: Mapped[Decimal] = mapped_column(
        Numeric(8, 3), nullable=False
    )


class CommerceOrder(Base):
    __tablename__ = "commerce_orders"
    __table_args__ = (
        Index("ix_commerce_orders_tenant_order", "tenant_id", "order_id", unique=True),
        Index("ix_commerce_orders_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: prefixed_id("ord")
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    customer: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    value_usd: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    risk: Mapped[str | None] = mapped_column(String(240))


class CustomerHealthRecord(Base):
    __tablename__ = "customer_health"
    __table_args__ = (
        Index(
            "ix_customer_health_tenant_customer",
            "tenant_id",
            "customer_id",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: prefixed_id("cus")
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    customer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    health_score: Mapped[int] = mapped_column(Integer, nullable=False)
    segment: Mapped[str] = mapped_column(String(40), nullable=False)
    lifetime_value_usd: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    open_support_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(300), nullable=False)


class KnowledgeRecord(Base):
    __tablename__ = "knowledge_records"
    __table_args__ = (Index("ix_knowledge_records_tenant", "tenant_id"),)

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: prefixed_id("doc")
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    section: Mapped[str] = mapped_column(String(120), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)


class InventoryRecord(Base):
    __tablename__ = "inventory_records"
    __table_args__ = (
        Index("ix_inventory_records_tenant_warehouse", "tenant_id", "warehouse"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: prefixed_id("inv")
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    warehouse: Mapped[str] = mapped_column(String(32), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    days_of_cover: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
