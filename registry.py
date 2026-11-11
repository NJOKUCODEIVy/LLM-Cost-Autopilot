"""
Model registry for the LLM Cost Autopilot.

Each entry describes one model the router can send requests to.
Prices are the providers' published paid rates in USD per 1 million tokens,
checked November 2026. We test on free tiers, but we calculate cost at paid
rates so the numbers show what each request would cost at scale.

avg_latency and quality_tier come from the Phase 1 baseline test
(10 prompts x 4 models). Revisit tiers once Phase 3 can judge open-ended answers.
"""

from dataclasses import dataclass


@dataclass
class ModelConfig:
    name: str                       # Short nickname used in our code
    provider: str                   # "groq" or "gemini"
    model_id: str                   # Exact model ID the provider's API expects
    input_cost_per_million: float   # USD per 1M input tokens
    output_cost_per_million: float  # USD per 1M output tokens (includes thinking tokens)
    avg_latency: float              # Average seconds per request, measured in the baseline
    quality_tier: str               # "low", "medium", or "high"

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        """Return the USD cost of one request with these token counts."""
        return (
            input_tokens / 1_000_000 * self.input_cost_per_million
            + output_tokens / 1_000_000 * self.output_cost_per_million
        )


MODEL_REGISTRY = {
    "gpt-oss-20b": ModelConfig(
        name="gpt-oss-20b",
        provider="groq",
        model_id="openai/gpt-oss-20b",
        input_cost_per_million=0.075,
        output_cost_per_million=0.30,
        avg_latency=0.79,
        quality_tier="low",
    ),
    "gpt-oss-120b": ModelConfig(
        name="gpt-oss-120b",
        provider="groq",
        model_id="openai/gpt-oss-120b",
        input_cost_per_million=0.15,
        output_cost_per_million=0.60,
        avg_latency=0.84,
        quality_tier="high",  # Baseline: 5/5 correct, including the multi-step reasoning question
    ),
    "gemini-3.5-flash-lite": ModelConfig(
        name="gemini-3.5-flash-lite",
        provider="gemini",
        model_id="gemini-3.5-flash-lite",
        # Replaced gemini-3.8-flash, which took 4-11 minutes per request on the free tier
        input_cost_per_million=0.30,
        output_cost_per_million=2.50,
        avg_latency=3.85,
        quality_tier="medium",
    ),
    "qwen3.8-27b": ModelConfig(
        name="qwen3.8-27b",
        provider="groq",
        model_id="qwen/qwen3.8-27b",  # Preview model on Groq; may change or be removed
        input_cost_per_million=0.80,
        output_cost_per_million=4.00,
        avg_latency=2.07,
        quality_tier="medium",  # Baseline: most expensive, and missed the train-time question
    ),
}


if __name__ == "__main__":
    # Quick check: what would your earlier Groq test (78 in, 251 out) cost on each model?
    input_tokens, output_tokens = 78, 251
    print(f"Cost of a request with {input_tokens} input and {output_tokens} output tokens:\n")
    for model in MODEL_REGISTRY.values():
        cost = model.cost(input_tokens, output_tokens)
        print(f"  {model.name:<22} {model.quality_tier:<7} ${cost:.7f}")