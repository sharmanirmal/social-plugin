"""Anthropic SDK wrapper for Claude API."""

from __future__ import annotations

import os
from dataclasses import dataclass

import anthropic

from social_plugin.utils.logger import get_logger
from social_plugin.utils.retry import with_retry

logger = get_logger()


# Approximate pricing per 1M tokens (Sonnet 4.5)
INPUT_COST_PER_M = 3.00
OUTPUT_COST_PER_M = 15.00


@dataclass
class GenerationResult:
    """Result from a Claude generation call."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float


class ClaudeClient:
    """Wrapper around the Anthropic API."""

    def __init__(self, model: str = "claude-sonnet-4-5-20250514", max_tokens: int = 4096, temperature: float = 0.7):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in environment")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    @with_retry(max_attempts=3, retry_on=(anthropic.APIError, anthropic.APIConnectionError))
    def generate(self, system_prompt: str, user_prompt: str) -> GenerationResult:
        """Generate content using Claude."""
        logger.info("Generating with %s (max_tokens=%d, temp=%.1f)", self.model, self.max_tokens, self.temperature)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = response.content[0].text
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        total_tokens = input_tokens + output_tokens

        cost = (input_tokens / 1_000_000 * INPUT_COST_PER_M) + (output_tokens / 1_000_000 * OUTPUT_COST_PER_M)

        logger.info(
            "Generated %d chars (%d input + %d output tokens, ~$%.4f)",
            len(text), input_tokens, output_tokens, cost,
        )

        return GenerationResult(
            text=text,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=cost,
        )
