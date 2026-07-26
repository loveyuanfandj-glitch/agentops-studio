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


class DeepSeekProvider:
    def __init__(self, settings: Settings) -> None:
        if not settings.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is required when AGENT_PROVIDER=deepseek")
        self.client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            max_retries=2,
        )
        self.model = settings.deepseek_model

    async def respond(
        self,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        instructions: str,
    ) -> ProviderTurn:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=self._messages(input_items, instructions),
                tools=self._tools(tools),
                stream=False,
                extra_body={"thinking": {"type": "disabled"}},
            )
        except Exception as exc:
            raise ProviderError("provider_request_failed", str(exc)) from exc

        message = response.choices[0].message
        output_items: list[dict[str, Any]] = []
        tool_calls: list[ToolCall] = []
        for call in message.tool_calls or []:
            try:
                arguments = json.loads(call.function.arguments)
            except json.JSONDecodeError as exc:
                raise ProviderError("invalid_tool_arguments", str(exc)) from exc
            output_items.append(
                {
                    "type": "function_call",
                    "call_id": call.id,
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                }
            )
            tool_calls.append(
                ToolCall(
                    call_id=call.id,
                    name=call.function.name,
                    arguments=arguments,
                )
            )

        final_text = (message.content or None) if not tool_calls else None
        if final_text:
            output_items.append(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": final_text}],
                }
            )

        usage = response.usage
        return ProviderTurn(
            output_items=output_items,
            tool_calls=tool_calls,
            final_text=final_text,
            usage=TokenUsage(
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                cached_tokens=(
                    getattr(usage, "prompt_cache_hit_tokens", 0) or 0
                    if usage
                    else 0
                ),
            ),
        )

    @staticmethod
    def _messages(
        input_items: list[dict[str, Any]], instructions: str
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": instructions}
        ]
        index = 0
        while index < len(input_items):
            item = input_items[index]
            if item.get("type") == "function_call":
                calls: list[dict[str, Any]] = []
                while (
                    index < len(input_items)
                    and input_items[index].get("type") == "function_call"
                ):
                    call = input_items[index]
                    calls.append(
                        {
                            "id": call["call_id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": call["arguments"],
                            },
                        }
                    )
                    index += 1
                messages.append(
                    {"role": "assistant", "content": "", "tool_calls": calls}
                )
                continue
            if item.get("type") == "function_call_output":
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": item["call_id"],
                        "content": item["output"],
                    }
                )
            elif item.get("role") in {"user", "assistant"}:
                messages.append(
                    {
                        "role": item["role"],
                        "content": DeepSeekProvider._text_content(item.get("content")),
                    }
                )
            index += 1
        return messages

    @staticmethod
    def _text_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("text")
            )
        return ""

    @staticmethod
    def _tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                },
            }
            for tool in tools
        ]


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
    if settings.agent_provider == "deepseek":
        return DeepSeekProvider(settings)
    return MockProvider()
