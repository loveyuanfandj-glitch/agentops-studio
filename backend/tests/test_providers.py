from __future__ import annotations

from types import SimpleNamespace

import pytest

from agentops.config import Settings
from agentops.providers import DeepSeekProvider, build_provider
from agentops.tools import ToolRegistry


class FakeCompletions:
    def __init__(self, response) -> None:
        self.response = response
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


# Validates the DeepSeek provider boundary, including model configuration, tool schema
# conversion, disabled thinking mode, tool-call parsing, and provider token usage.
async def test_deepseek_provider_maps_chat_completion_tool_calls() -> None:
    tool_call = SimpleNamespace(
        id="call_orders",
        function=SimpleNamespace(
            name="search_orders",
            arguments='{"status":"at_risk","minimum_value_usd":2500,"limit":5}',
        ),
    )
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="I will inspect the orders.", tool_calls=[tool_call]
                )
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=320,
            completion_tokens=42,
            prompt_cache_hit_tokens=120,
        ),
    )
    completions = FakeCompletions(response)
    provider = object.__new__(DeepSeekProvider)
    provider.client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )
    provider.model = "deepseek-v4-flash"

    turn = await provider.respond(
        [{"role": "user", "content": "Find risky orders"}],
        ToolRegistry(timeout_seconds=1, retry_attempts=0).schemas(),
        "Use tools for business data.",
    )

    assert completions.kwargs["model"] == "deepseek-v4-flash"
    assert completions.kwargs["extra_body"] == {
        "thinking": {"type": "disabled"}
    }
    assert completions.kwargs["messages"][0]["role"] == "system"
    assert completions.kwargs["tools"][0]["function"]["name"] == (
        "get_revenue_summary"
    )
    assert turn.tool_calls[0].call_id == "call_orders"
    assert turn.tool_calls[0].arguments["limit"] == 5
    assert turn.final_text is None
    assert len(turn.output_items) == 1
    assert turn.usage.input_tokens == 320
    assert turn.usage.cached_tokens == 120


# Ensures prior assistant tool calls and correlated function outputs are replayed in
# the OpenAI-compatible Chat Completions message format required by DeepSeek.
def test_deepseek_provider_replays_tool_results() -> None:
    messages = DeepSeekProvider._messages(
        [
            {"role": "user", "content": "Review revenue risk"},
            {
                "type": "function_call",
                "call_id": "call_revenue",
                "name": "get_revenue_summary",
                "arguments": '{"start_date":"2026-07-01","end_date":"2026-07-26","channel":"all"}',
            },
            {
                "type": "function_call_output",
                "call_id": "call_revenue",
                "output": '{"ok":true,"data":{"gross_revenue":184620.42}}',
            },
        ],
        "Use tools.",
    )

    assert [message["role"] for message in messages] == [
        "system",
        "user",
        "assistant",
        "tool",
    ]
    assert messages[2]["tool_calls"][0]["id"] == "call_revenue"
    assert messages[3]["tool_call_id"] == "call_revenue"


# Confirms the DeepSeek provider cannot be selected without an explicit API key,
# preventing an apparently live deployment from silently falling back to mock data.
def test_deepseek_provider_requires_api_key() -> None:
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        build_provider(
            Settings(agent_provider="deepseek", deepseek_api_key=None)
        )
