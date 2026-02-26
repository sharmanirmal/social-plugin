"""Content safety checks — profanity filter and compliance."""

from __future__ import annotations

import re
from dataclasses import dataclass

from better_profanity import profanity

from social_plugin.utils.logger import get_logger

logger = get_logger()


@dataclass
class SafetyResult:
    """Result of content safety check."""

    is_safe: bool
    issues: list[str]

    @property
    def summary(self) -> str:
        if self.is_safe:
            return "Content passed safety checks"
        return "Content flagged: " + "; ".join(self.issues)


class ContentSafety:
    """Profanity filter and content safety checker."""

    def __init__(self, blocked_words: list[str] | None = None, compliance_note: str = ""):
        profanity.load_censor_words()
        self.blocked_words = [w.lower() for w in (blocked_words or [])]
        self.compliance_note = compliance_note
        if self.blocked_words:
            profanity.add_censor_words(self.blocked_words)

    def check(self, content: str) -> SafetyResult:
        """Run all safety checks on content."""
        issues: list[str] = []

        # Profanity check
        if profanity.contains_profanity(content):
            issues.append("Contains profanity or vulgar language")

        # Custom blocked words
        content_lower = content.lower()
        for word in self.blocked_words:
            if word in content_lower:
                issues.append(f"Contains blocked word: '{word}'")

        # Basic compliance checks
        compliance_issues = self._check_compliance(content)
        issues.extend(compliance_issues)

        result = SafetyResult(is_safe=len(issues) == 0, issues=issues)
        if not result.is_safe:
            logger.warning("Safety check failed: %s", result.summary)
        return result

    def _check_compliance(self, content: str) -> list[str]:
        """Basic compliance checks."""
        issues: list[str] = []
        content_lower = content.lower()

        # Check for financial advice patterns
        financial_patterns = [
            r"\b(invest|buy|sell)\s+(now|today|immediately)\b",
            r"\bguaranteed\s+(returns?|profit)\b",
            r"\bnot\s+financial\s+advice\b",  # Ironically, this disclaimer often signals advice
        ]
        for pattern in financial_patterns:
            if re.search(pattern, content_lower):
                issues.append("May contain financial advice language")
                break

        # Check for medical claims
        medical_patterns = [
            r"\b(cure[sd]?|treat[sd]?|heal[sd]?)\s+(disease|illness|cancer|covid)\b",
        ]
        for pattern in medical_patterns:
            if re.search(pattern, content_lower):
                issues.append("May contain medical claims")
                break

        return issues

    def censor(self, content: str) -> str:
        """Censor profanity in content (replace with ****)."""
        return profanity.censor(content)
