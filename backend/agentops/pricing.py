from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ModelRate:
    input_per_million: Decimal
    output_per_million: Decimal
    cached_input_per_million: Decimal | None = None


# Defaults verified against the OpenAI model catalog on 2026-07-26. Production
# deployments should treat pricing as configuration and review it regularly.
MODEL_RATES: dict[str, ModelRate] = {
    "gpt-5.6": ModelRate(Decimal("5"), Decimal("30")),
    "gpt-5.6-sol": ModelRate(Decimal("5"), Decimal("30")),
    "gpt-5.6-terra": ModelRate(Decimal("2.5"), Decimal("15")),
    "gpt-5.6-luna": ModelRate(Decimal("1"), Decimal("6")),
    "deepseek-v4-flash": ModelRate(
        Decimal("0.14"), Decimal("0.28"), Decimal("0.0028")
    ),
    "deepseek-v4-pro": ModelRate(
        Decimal("0.435"), Decimal("0.87"), Decimal("0.003625")
    ),
}


def estimate_cost(
    model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0
) -> Decimal:
    rate = MODEL_RATES.get(model, MODEL_RATES["gpt-5.6-terra"])
    billable_cached = min(cached_tokens, input_tokens)
    uncached_tokens = input_tokens - billable_cached
    cached_rate = rate.cached_input_per_million or rate.input_per_million
    total = (
        Decimal(uncached_tokens) * rate.input_per_million
        + Decimal(billable_cached) * cached_rate
        + Decimal(output_tokens) * rate.output_per_million
    ) / Decimal(1_000_000)
    return total.quantize(Decimal("0.00000001"))
