from typing import Dict, Optional
from src.observability.models import CostBreakdown, ModelPricingConfig, TokenMetrics, TokenStatus


DEFAULT_PRICING: Dict[str, ModelPricingConfig] = {
    "llama-3.1-8b-instant": ModelPricingConfig(
        model_name="llama-3.1-8b-instant",
        input_cost_per_1m=0.05,
        output_cost_per_1m=0.08,
    ),
    "llama-3.3-70b-versatile": ModelPricingConfig(
        model_name="llama-3.3-70b-versatile",
        input_cost_per_1m=0.59,
        output_cost_per_1m=0.79,
    ),
    "gpt-4o": ModelPricingConfig(
        model_name="gpt-4o",
        input_cost_per_1m=2.50,
        output_cost_per_1m=10.00,
    ),
    "openai/gpt-oss-20b": ModelPricingConfig(
        model_name="openai/gpt-oss-20b",
        input_cost_per_1m=0.075,
        output_cost_per_1m=0.30,
    ),
}


def _normalize_model_name(name: str) -> str:
    if not name:
        return ""
    name = str(name).strip().lower()
    if "/" in name:
        name = name.split("/")[-1]
    return name


class CostCalculator:
    def __init__(self, pricing_catalog: Optional[Dict[str, ModelPricingConfig]] = None):
        self.pricing_catalog = pricing_catalog if pricing_catalog is not None else DEFAULT_PRICING

    def calculate_cost(
        self,
        model_name: Optional[str],
        token_metrics: TokenMetrics
    ) -> CostBreakdown:
        if (
            token_metrics.status == TokenStatus.UNAVAILABLE
            or token_metrics.input_tokens is None
            or token_metrics.output_tokens is None
            or not model_name
        ):
            return CostBreakdown(
                input_cost=None,
                output_cost=None,
                total_cost=None,
                currency="USD",
                status=TokenStatus.UNAVAILABLE,
            )

        norm_target = _normalize_model_name(model_name)
        matched_pricing: Optional[ModelPricingConfig] = None

        # Direct key lookup first
        if model_name in self.pricing_catalog:
            matched_pricing = self.pricing_catalog[model_name]
        else:
            # Case-insensitive / prefix-insensitive lookup
            for key, pricing in self.pricing_catalog.items():
                if _normalize_model_name(key) == norm_target:
                    matched_pricing = pricing
                    break

        if not matched_pricing:
            return CostBreakdown(
                input_cost=None,
                output_cost=None,
                total_cost=None,
                currency="USD",
                status=TokenStatus.UNAVAILABLE,
            )

        inp_cost = (token_metrics.input_tokens / 1_000_000.0) * matched_pricing.input_cost_per_1m
        out_cost = (token_metrics.output_tokens / 1_000_000.0) * matched_pricing.output_cost_per_1m
        total_cost = round(inp_cost + out_cost, 6)

        return CostBreakdown(
            input_cost=round(inp_cost, 6),
            output_cost=round(out_cost, 6),
            total_cost=total_cost,
            currency=matched_pricing.currency,
            # Derived from token counts x list pricing, not a provider bill.
            status=TokenStatus.ESTIMATED,
        )