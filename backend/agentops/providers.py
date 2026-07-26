from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from openai import AsyncOpenAI

from agentops.config import Settings


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ProviderTurn:
    output_items: list[dict[str, Any]]
    tool_calls: list[ToolCall] = field(default_factory=list)
    final_text: str | None = None
    usage: TokenUsage = field(default_factory=TokenUsage)


class AgentProvider(Protocol):
    async def respond(
        self,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        instructions: str,
    ) -> ProviderTurn: ...


class ProviderError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class OpenAIProvider:
    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when AGENT_PROVIDER=openai")
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, max_retries=2)
        self.model = settings.openai_model
        self.store_responses = settings.openai_store_responses

    async def respond(
        self,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        instructions: str,
    ) -> ProviderTurn:
        try:
            response = await self.client.responses.create(
                model=self.model,
                instructions=instructions,
                input=input_items,
                tools=tools,
                parallel_tool_calls=False,
                store=self.store_responses,
            )
        except Exception as exc:
            raise ProviderError("provider_request_failed", str(exc)) from exc

        output_items = [item.model_dump(exclude_none=True) for item in response.output]
        tool_calls: list[ToolCall] = []
        for item in response.output:
            if item.type != "function_call":
                continue
            try:
                arguments = json.loads(item.arguments)
            except json.JSONDecodeError as exc:
                raise ProviderError("invalid_tool_arguments", str(exc)) from exc
            tool_calls.append(
                ToolCall(call_id=item.call_id, name=item.name, arguments=arguments)
            )

        usage = response.usage
        cached_tokens = 0
        if usage and usage.input_tokens_details:
            cached_tokens = usage.input_tokens_details.cached_tokens
        return ProviderTurn(
            output_items=output_items,
            tool_calls=tool_calls,
            final_text=response.output_text or None,
            usage=TokenUsage(
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                cached_tokens=cached_tokens,
            ),
        )


class MockProvider:
    """Deterministic provider that demonstrates the complete agent loop without an API key."""

    async def respond(
        self,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        instructions: str,
    ) -> ProviderTurn:
        del tools, instructions
        tool_outputs = [item for item in input_items if item.get("type") == "function_call_output"]
        step = len(tool_outputs)
        if step == 0:
            return self._tool_turn(
                "call_revenue",
                "get_revenue_summary",
                {"start_date": "2026-07-01", "end_date": "2026-07-26", "channel": "all"},
                640,
                54,
            )
        if step == 1:
            return self._tool_turn(
                "call_orders",
                "search_orders",
                {"status": "at_risk", "minimum_value_usd": 2500, "limit": 5},
                890,
                47,
            )
        if step == 2:
            return self._tool_turn(
                "call_customer",
                "get_customer_health",
                {"customer_id": "CUS-2041"},
                1_120,
                38,
            )

        answer = (
            "Revenue is up 12.4% for the period, but two high-value orders need attention. "
            "Prioritize ORD-10482 ($4,820): Avery Stone has a health score of 46 and two open "
            "support cases after repeated payment failures. Assign an account owner and resolve "
            "the payment method today. Next, expedite ORD-10471 ($3,680) and send Morgan Labs a "
            "proactive fulfilment update. These actions protect $8,500 in at-risk revenue."
        )
        return ProviderTurn(
            output_items=[
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": answer}],
                }
            ],
            final_text=answer,
            usage=TokenUsage(input_tokens=1_360, output_tokens=142),
        )

    @staticmethod
    def _tool_turn(
        call_id: str,
        name: str,
        arguments: dict[str, Any],
        input_tokens: int,
        output_tokens: int,
    ) -> ProviderTurn:
        item = {
            "type": "function_call",
            "call_id": call_id,
            "name": name,
            "arguments": json.dumps(arguments),
        }
        return ProviderTurn(
            output_items=[item],
            tool_calls=[ToolCall(call_id=call_id, name=name, arguments=arguments)],
            usage=TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
        )


def build_provider(settings: Settings) -> AgentProvider:
    if settings.agent_provider == "openai":
        return OpenAIProvider(settings)
    return MockProvider()
