from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    plan: str
    monthly_budget_usd: Decimal


class ConversationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    created_at: datetime


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageRead] = Field(default_factory=list)


class RunStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sequence: int
    kind: str
    name: str
    status: str
    arguments: dict | None
    output: dict | None
    duration_ms: int | None
    error_code: str | None
    created_at: datetime


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    conversation_id: str
    status: str
    model: str
    prompt: str
    answer: str | None
    error_code: str | None
    guardrail_reason: str | None
    steps_count: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: Decimal
    latency_ms: int | None
    started_at: datetime
    completed_at: datetime | None
    steps: list[RunStepRead] = Field(default_factory=list)


class AgentResponse(BaseModel):
    conversation_id: str
    run: RunRead


class MetricPoint(BaseModel):
    bucket: str
    runs: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


class MetricsSummary(BaseModel):
    total_runs: int
    successful_runs: int
    guarded_runs: int
    failed_runs: int
    success_rate: float
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: Decimal
    average_latency_ms: float
    timeseries: list[MetricPoint]
