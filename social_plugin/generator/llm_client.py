"""Multi-provider LLM client abstraction (Anthropic Claude, OpenAI, Google Gemini)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from social_plugin.utils.logger import get_logger
from social_plugin.utils.retry import with_retry

logger = get_logger()


@dataclass
class GenerationResult:
    """Result from an LLM generation call."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM clients."""

    def generate(self, system_prompt: str, user_prompt: str) -> GenerationResult: ...


# =============================================================================
# Cost tables (per 1M tokens)
# =============================================================================

ANTHROPIC_COSTS = {
    "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-6": {"input": 15.00, "output": 75.00},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
}

OPENAI_COSTS = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "o1": {"input": 15.00, "output": 60.00},
    "o1-mini": {"input": 3.00, "output": 12.00},
    "o3-mini": {"input": 1.10, "output": 4.40},
}

GOOGLE_COSTS = {
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int, cost_table: dict) -> float:
    """Estimate cost using the closest matching model in the cost table."""
    # Try exact match first
    if model in cost_table:
        costs = cost_table[model]
    else:
        # Try prefix match (e.g. "gpt-4o-2024-08-06" matches "gpt-4o")
        matched = None
        for key in cost_table:
            if model.startswith(key):
                matched = cost_table[key]
                break
        costs = matched or {"input": 0.0, "output": 0.0}

    return (input_tokens / 1_000_000 * costs["input"]) + (output_tokens / 1_000_000 * costs["output"])


# =============================================================================
# Claude Client
# =============================================================================

class ClaudeClient:
    """Anthropic Claude API client."""

    def __init__(self, model: str = "claude-sonnet-4-5-20250929", max_tokens: int = 4096, temperature: float = 0.7):
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in environment")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._anthropic = anthropic  # Keep reference for retry exception types

    def generate(self, system_prompt: str, user_prompt: str) -> GenerationResult:
        import anthropic

        @with_retry(max_attempts=3, retry_on=(anthropic.APIError, anthropic.APIConnectionError))
        def _call():
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
            cost = _estimate_cost(self.model, input_tokens, output_tokens, ANTHROPIC_COSTS)

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

        return _call()


# =============================================================================
# OpenAI Client
# =============================================================================

class OpenAIClient:
    """OpenAI API client (GPT-4o, o1, etc.)."""

    def __init__(self, model: str = "gpt-4o", max_tokens: int = 4096, temperature: float = 0.7):
        import openai

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")

        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._is_reasoning = model.startswith(("o1", "o3"))

    def generate(self, system_prompt: str, user_prompt: str) -> GenerationResult:
        import openai

        @with_retry(max_attempts=3, retry_on=(openai.APIError, openai.APIConnectionError))
        def _call():
            logger.info("Generating with %s (max_tokens=%d, temp=%.1f)", self.model, self.max_tokens, self.temperature)

            messages = []
            if self._is_reasoning:
                # o1/o3 models don't support system messages; prepend to user prompt
                messages.append({"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"})
            else:
                messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": user_prompt})

            kwargs = {
                "model": self.model,
                "messages": messages,
            }

            if self._is_reasoning:
                kwargs["max_completion_tokens"] = self.max_tokens
            else:
                kwargs["max_tokens"] = self.max_tokens
                kwargs["temperature"] = self.temperature

            response = self.client.chat.completions.create(**kwargs)

            text = response.choices[0].message.content or ""
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0
            total_tokens = input_tokens + output_tokens
            cost = _estimate_cost(self.model, input_tokens, output_tokens, OPENAI_COSTS)

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

        return _call()


# =============================================================================
# Google Gemini Client
# =============================================================================

class GeminiClient:
    """Google Gemini API client."""

    def __init__(self, model: str = "gemini-2.0-flash", max_tokens: int = 4096, temperature: float = 0.7):
        import google.generativeai as genai

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set in environment")

        genai.configure(api_key=api_key)
        self.genai = genai
        self.model_name = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.model = genai.GenerativeModel(
            model_name=model,
            system_instruction=None,  # Set per-call
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )

    def generate(self, system_prompt: str, user_prompt: str) -> GenerationResult:
        @with_retry(max_attempts=3, retry_on=(Exception,))
        def _call():
            logger.info("Generating with %s (max_tokens=%d, temp=%.1f)", self.model_name, self.max_tokens, self.temperature)

            # Create model with system instruction for this call
            model = self.genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt,
                generation_config=self.genai.types.GenerationConfig(
                    max_output_tokens=self.max_tokens,
                    temperature=self.temperature,
                ),
            )

            response = model.generate_content(user_prompt)

            text = response.text
            # Gemini usage metadata
            usage = getattr(response, "usage_metadata", None)
            input_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
            output_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0
            total_tokens = input_tokens + output_tokens
            cost = _estimate_cost(self.model_name, input_tokens, output_tokens, GOOGLE_COSTS)

            logger.info(
                "Generated %d chars (%d input + %d output tokens, ~$%.4f)",
                len(text), input_tokens, output_tokens, cost,
            )

            return GenerationResult(
                text=text,
                model=self.model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost=cost,
            )

        return _call()


# =============================================================================
# Factory
# =============================================================================

_PROVIDER_MODEL_PREFIXES = {
    "anthropic": ("claude-",),
    "openai": ("gpt-", "o1", "o3"),
    "google": ("gemini-",),
}


def detect_provider(model: str) -> str:
    """Auto-detect provider from model name."""
    for provider, prefixes in _PROVIDER_MODEL_PREFIXES.items():
        if any(model.startswith(p) for p in prefixes):
            return provider
    raise ValueError(
        f"Cannot auto-detect provider for model '{model}'. "
        f"Set 'generation.provider' in config to 'anthropic', 'openai', or 'google'."
    )


def create_llm_client(
    model: str,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    provider: str | None = None,
) -> LLMClient:
    """Create an LLM client for the given provider and model.

    If provider is None, auto-detects from model name.
    """
    if provider is None:
        provider = detect_provider(model)

    if provider == "anthropic":
        return ClaudeClient(model=model, max_tokens=max_tokens, temperature=temperature)
    elif provider == "openai":
        return OpenAIClient(model=model, max_tokens=max_tokens, temperature=temperature)
    elif provider == "google":
        return GeminiClient(model=model, max_tokens=max_tokens, temperature=temperature)
    else:
        raise ValueError(f"Unknown provider '{provider}'. Use 'anthropic', 'openai', or 'google'.")
