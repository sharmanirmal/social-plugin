"""Tests for prompt templates."""

from social_plugin.generator.prompts import (
    build_linkedin_system_prompt,
    build_regen_prompt,
    build_tweet_system_prompt,
    build_user_prompt,
)


def test_tweet_system_prompt():
    """Tweet system prompt includes key constraints."""
    prompt = build_tweet_system_prompt(max_length=280, tone="casual", hashtags=["#AI"])
    assert "280" in prompt
    assert "casual" in prompt
    assert "#AI" in prompt


def test_linkedin_system_prompt():
    """LinkedIn system prompt includes key constraints."""
    prompt = build_linkedin_system_prompt(max_length=3000, tone="professional")
    assert "3000" in prompt
    assert "professional" in prompt
    assert "question" in prompt.lower()


def test_user_prompt_with_trends():
    """User prompt includes trend data."""
    trends = [{"title": "Robot breakthrough", "summary": "New robot achieves..."}]
    prompt = build_user_prompt("Twitter", trends=trends)
    assert "Robot breakthrough" in prompt
    assert "Twitter" in prompt


def test_user_prompt_without_trends():
    """User prompt handles missing trends gracefully."""
    prompt = build_user_prompt("LinkedIn")
    assert "general" in prompt.lower() or "No specific trends" in prompt


def test_user_prompt_with_sources():
    """User prompt includes source material."""
    sources = [{"title": "Paper", "content": "Interesting findings about embodied AI..."}]
    prompt = build_user_prompt("Twitter", sources=sources)
    assert "Paper" in prompt
    assert "embodied AI" in prompt


def test_regen_prompt():
    """Regen prompt includes original and new tone."""
    prompt = build_regen_prompt("Original tweet text", "more casual", "tweet")
    assert "Original tweet text" in prompt
    assert "more casual" in prompt
