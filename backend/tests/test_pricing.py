from decimal import Decimal

from agentops.pricing import estimate_cost


# Verifies DeepSeek cache-hit tokens use the lower cached-input rate while remaining
# input and output tokens use their normal model-specific rates.
def test_deepseek_cost_uses_cached_input_rate() -> None:
    cost = estimate_cost(
        "deepseek-v4-flash",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cached_tokens=250_000,
    )

    assert cost == Decimal("0.38570000")
