"""Tests for content safety module."""

import pytest

from social_plugin.generator.safety import ContentSafety


@pytest.fixture
def safety():
    return ContentSafety(blocked_words=["badword"], compliance_note="No financial advice")


def test_clean_content_passes(safety):
    """Clean content passes safety checks."""
    result = safety.check("Physical AI is transforming robotics manufacturing.")
    assert result.is_safe
    assert len(result.issues) == 0


def test_blocked_words(safety):
    """Blocked words are caught."""
    result = safety.check("This contains badword in the text.")
    assert not result.is_safe
    assert any("blocked word" in issue.lower() for issue in result.issues)


def test_compliance_financial(safety):
    """Financial advice patterns are flagged."""
    result = safety.check("You should invest now in robotics stocks for guaranteed returns.")
    assert not result.is_safe
    assert any("financial" in issue.lower() for issue in result.issues)


def test_compliance_medical(safety):
    """Medical claims are flagged."""
    result = safety.check("This robot cured cancer in a lab.")
    assert not result.is_safe
    assert any("medical" in issue.lower() for issue in result.issues)


def test_censor(safety):
    """Censor replaces profanity with asterisks."""
    # better-profanity has its own word list
    censored = safety.censor("This is a clean sentence.")
    assert "****" not in censored


def test_safety_summary(safety):
    """Safety result summary formats correctly."""
    result = safety.check("Clean content here.")
    assert "passed" in result.summary.lower()
