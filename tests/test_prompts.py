"""Tests for prompt templates."""

from social_plugin.generator.prompts import (
    build_add_context_prompt,
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


def test_tweet_system_prompt_default_length():
    """Default tweet max_length is 280 (standard accounts)."""
    prompt = build_tweet_system_prompt(tone="professional")
    assert "280" in prompt
    assert "concise" in prompt.lower()


def test_tweet_system_prompt_long_form():
    """Long-form tweet prompt for X Premium accounts."""
    prompt = build_tweet_system_prompt(max_length=25000)
    assert "25000" in prompt
    assert "200-600 characters" in prompt


def test_tweet_system_prompt_is_rewrite():
    """When is_rewrite=True, length note is flexible."""
    prompt = build_tweet_system_prompt(is_rewrite=True)
    assert "flexible" in prompt.lower()
    assert "4000" not in prompt  # Should not mention specific limit during rewrites


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


def test_user_prompt_includes_trend_urls():
    """User prompt includes URLs from trends."""
    trends = [
        {"title": "Robot breakthrough", "summary": "New robot", "url": "https://example.com/article"}
    ]
    prompt = build_user_prompt("Twitter", trends=trends)
    assert "https://example.com/article" in prompt


def test_user_prompt_includes_source_paths():
    """User prompt includes source paths for reference."""
    sources = [
        {"title": "Research Paper", "content": "AI findings...", "source_path": "/docs/paper.pdf"}
    ]
    prompt = build_user_prompt("Twitter", sources=sources)
    assert "/docs/paper.pdf" in prompt
    assert "source:" in prompt


def test_user_prompt_with_previous_drafts():
    """User prompt includes previous drafts to avoid repetition."""
    previous = ["Previous tweet about robotics advances", "Another tweet about embodied AI"]
    prompt = build_user_prompt("Twitter", previous_drafts=previous)
    assert "SUBSTANTIALLY different" in prompt
    assert "Previous tweet about robotics" in prompt
    assert "Another tweet about embodied AI" in prompt


def test_user_prompt_no_previous_drafts_section_when_empty():
    """User prompt omits previous drafts section when none exist."""
    prompt = build_user_prompt("Twitter")
    assert "already generated" not in prompt


def test_user_prompt_empty_sources_note():
    """User prompt includes note when no source documents available."""
    prompt = build_user_prompt("Twitter", sources=None)
    assert "No reference documents available" in prompt


def test_user_prompt_url_instruction_twitter():
    """Twitter prompts include URL instruction."""
    prompt = build_user_prompt("Twitter")
    assert "source URL" in prompt


def test_user_prompt_url_instruction_linkedin():
    """LinkedIn prompts include URL instruction."""
    prompt = build_user_prompt("LinkedIn")
    assert "source URLs" in prompt


def test_regen_prompt():
    """Regen prompt includes original and new tone."""
    prompt = build_regen_prompt("Original tweet text", "more casual", "tweet")
    assert "Original tweet text" in prompt
    assert "more casual" in prompt


def test_regen_prompt_encourages_restructure():
    """Regen prompt encourages genuinely different output."""
    prompt = build_regen_prompt("Original text", "bold", "tweet")
    assert "restructure" in prompt
    assert "genuinely different" in prompt


def test_add_context_prompt():
    """Add context prompt instructs substantial rewrite."""
    prompt = build_add_context_prompt(
        "Original post about robots", "New study shows 50% efficiency gain", "twitter"
    )
    assert "Original post about robots" in prompt
    assert "50% efficiency gain" in prompt
    assert "Substantially rewrite" in prompt
    assert "NOT simply append" in prompt


def test_add_context_prompt_output_format():
    """Add context prompt asks for only the rewritten text."""
    prompt = build_add_context_prompt("Original", "New info", "linkedin")
    assert "Output ONLY the rewritten text" in prompt
