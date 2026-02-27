"""Tests for prompt templates."""

from social_plugin.generator.prompts import (
    build_add_context_prompt,
    build_linkedin_system_prompt,
    build_regen_prompt,
    build_rules_section,
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


# =============================================================================
# Feature A: Config-driven topic tests
# =============================================================================


def test_tweet_system_prompt_custom_topic():
    """Tweet system prompt uses custom topic."""
    prompt = build_tweet_system_prompt(topic="Quantum Computing")
    assert "Quantum Computing" in prompt


def test_linkedin_system_prompt_custom_topic():
    """LinkedIn system prompt uses custom topic."""
    prompt = build_linkedin_system_prompt(topic="Quantum Computing")
    assert "Quantum Computing" in prompt


def test_user_prompt_custom_topic():
    """User prompt uses custom topic."""
    prompt = build_user_prompt("Twitter", topic="Quantum Computing")
    assert "Quantum Computing" in prompt


def test_user_prompt_no_trends_custom_topic():
    """No-trends fallback uses custom topic."""
    prompt = build_user_prompt("Twitter", topic="Quantum Computing")
    assert "Quantum Computing" in prompt
    assert "No specific trends" in prompt


def test_no_hardcoded_physical_ai_when_custom_topic():
    """When custom topic is set, 'Physical AI' should not appear."""
    prompt = build_tweet_system_prompt(topic="Quantum Computing")
    assert "Physical AI" not in prompt
    prompt2 = build_linkedin_system_prompt(topic="Quantum Computing")
    assert "Physical AI" not in prompt2
    prompt3 = build_user_prompt("Twitter", topic="Quantum Computing")
    assert "Physical AI" not in prompt3


# =============================================================================
# Feature A: Hashtag tests
# =============================================================================


def test_tweet_prompt_custom_hashtags():
    """Tweet prompt uses custom hashtags."""
    prompt = build_tweet_system_prompt(hashtags=["#Quantum", "#Physics"])
    assert "#Quantum" in prompt
    assert "#Physics" in prompt


def test_linkedin_prompt_custom_hashtags():
    """LinkedIn prompt uses custom hashtags."""
    prompt = build_linkedin_system_prompt(hashtags=["#Quantum", "#Physics"])
    assert "#Quantum" in prompt
    assert "#Physics" in prompt


def test_tweet_prompt_empty_hashtags():
    """Tweet prompt handles empty hashtags list gracefully."""
    prompt = build_tweet_system_prompt(hashtags=[])
    # Should not crash; uses fallback text
    assert "relevant hashtags" in prompt


# =============================================================================
# Feature B: Rules tests
# =============================================================================


def test_build_rules_section_do_and_dont():
    """Rules section includes both DO and DON'T."""
    rules = {
        "do": ["Use data points", "Be specific"],
        "dont": ["No clickbait", "No hype"],
    }
    section = build_rules_section(rules)
    assert "Content rules:" in section
    assert "DO:" in section
    assert "DON'T:" in section
    assert "Use data points" in section
    assert "No clickbait" in section


def test_build_rules_section_do_only():
    """Rules section works with only DO rules."""
    rules = {"do": ["Use data points"], "dont": []}
    section = build_rules_section(rules)
    assert "DO:" in section
    assert "DON'T:" not in section


def test_build_rules_section_empty():
    """Rules section returns empty string for empty rules."""
    section = build_rules_section({"do": [], "dont": []})
    assert section == ""


def test_build_rules_section_none():
    """Rules section returns empty string for None."""
    section = build_rules_section(None)
    assert section == ""


def test_tweet_prompt_with_rules():
    """Tweet system prompt includes rules section."""
    rules = {"do": ["Be specific"], "dont": ["No hype"]}
    prompt = build_tweet_system_prompt(rules=rules)
    assert "Content rules:" in prompt
    assert "Be specific" in prompt
    assert "No hype" in prompt


def test_linkedin_prompt_with_rules():
    """LinkedIn system prompt includes rules section."""
    rules = {"do": ["Be specific"], "dont": ["No hype"]}
    prompt = build_linkedin_system_prompt(rules=rules)
    assert "Content rules:" in prompt
    assert "Be specific" in prompt


# =============================================================================
# Feature C: Style examples tests
# =============================================================================


def test_user_prompt_with_style_examples():
    """User prompt includes style examples."""
    examples = [
        "Boston Dynamics' Atlas does backflips. #Robotics",
        "Toyota Research achieves 94% success rate.",
    ]
    prompt = build_user_prompt("Twitter", style_examples=examples)
    assert "Boston Dynamics" in prompt
    assert "Toyota Research" in prompt
    assert "Match this voice" in prompt
    assert 'Example 1:' in prompt
    assert 'Example 2:' in prompt


def test_user_prompt_no_style_examples():
    """User prompt omits style section when no examples."""
    prompt = build_user_prompt("Twitter", style_examples=None)
    assert "Match this voice" not in prompt


# =============================================================================
# Feature D: Rejection/approval feedback tests
# =============================================================================


def test_user_prompt_with_rejection_feedback():
    """User prompt includes rejection feedback."""
    feedback = ["too generic", "needs more data"]
    prompt = build_user_prompt("Twitter", rejection_feedback=feedback)
    assert "things to AVOID" in prompt
    assert "too generic" in prompt
    assert "needs more data" in prompt


def test_user_prompt_with_approval_feedback():
    """User prompt includes approval feedback."""
    feedback = ["loved the data points", "great hook"]
    prompt = build_user_prompt("Twitter", approval_feedback=feedback)
    assert "things that worked WELL" in prompt
    assert "loved the data points" in prompt
    assert "great hook" in prompt


def test_user_prompt_with_both_feedback_types():
    """User prompt includes both rejection and approval feedback."""
    prompt = build_user_prompt(
        "Twitter",
        rejection_feedback=["too long"],
        approval_feedback=["good structure"],
    )
    assert "things to AVOID" in prompt
    assert "too long" in prompt
    assert "things that worked WELL" in prompt
    assert "good structure" in prompt


def test_user_prompt_without_feedback():
    """User prompt omits feedback sections when none provided."""
    prompt = build_user_prompt("Twitter")
    assert "things to AVOID" not in prompt
    assert "things that worked WELL" not in prompt
