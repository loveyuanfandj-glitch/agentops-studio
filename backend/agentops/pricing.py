from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ModelRate:
    input_per_million: Decimal
    output_per_million: Decimal


# Defaults verified against the OpenAI model catalog on 2026-07-26. Production
# deployments should treat pricing as configuration and review it regularly.
MODEL_RATES: dict[str, ModelRate] = {
    "gpt-5.6": ModelRate(Decimal("5"), Decimal("30")),
    "gpt-5.6-sol": ModelRate(Decimal("5"), Decimal("30")),
    "gpt-5.6-terra": ModelRate(Decimal("2.5"), Decimal("15")),
    "gpt-5.6-luna": ModelRate(Decimal("1"), Decimal("6")),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    rate = MODEL_RATES.get(model, MODEL_RATES["gpt-5.6-terra"])
    total = (
        Decimal(input_tokens) * rate.input_per_million
        + Decimal(output_tokens) * rate.output_per_million
    ) / Decimal(1_000_000)
    return total.quantize(Decimal("0.00000001"))
