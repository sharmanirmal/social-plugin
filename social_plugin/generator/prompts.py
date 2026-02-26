"""Platform-specific prompt templates for content generation."""

from __future__ import annotations


TWEET_SYSTEM_PROMPT = """\
You are an expert social media strategist specializing in Physical AI and Robotics content.
You create concise, engaging tweets that drive engagement in the tech community.

Guidelines:
- Write exactly ONE tweet
- Stay within {max_length} characters (including hashtags)
- Be insightful and thought-provoking, not generic
- Use a {tone} tone
- Include 1-2 relevant hashtags from: {hashtags}
- Reference specific trends or findings when possible
- No emojis unless they add genuine value
- {compliance_note}

Output ONLY the tweet text, nothing else. No quotes, no labels, no explanations."""


LINKEDIN_SYSTEM_PROMPT = """\
You are an expert social media strategist specializing in Physical AI and Robotics content.
You create engaging LinkedIn posts that establish thought leadership.

Guidelines:
- Write exactly ONE LinkedIn post
- Stay within {max_length} characters
- Use a {tone} tone
- Use line breaks for readability (LinkedIn rewards this)
- Start with a hook that grabs attention
- Include personal perspective or insight
- End with a question to drive comments
- Include 2-3 relevant hashtags from: {hashtags}
- {compliance_note}

Output ONLY the post text, nothing else. No quotes, no labels, no explanations."""


USER_PROMPT_TEMPLATE = """\
Create a {platform} post about Physical AI and Robotics.

{trends_section}

{sources_section}

{additional_context}"""


def build_tweet_system_prompt(
    max_length: int = 280,
    tone: str = "informative, thought-provoking, professional",
    hashtags: list[str] | None = None,
    compliance_note: str = "",
) -> str:
    return TWEET_SYSTEM_PROMPT.format(
        max_length=max_length,
        tone=tone,
        hashtags=", ".join(hashtags or ["#PhysicalAI", "#Robotics"]),
        compliance_note=compliance_note or "No disclaimers needed.",
    )


def build_linkedin_system_prompt(
    max_length: int = 3000,
    tone: str = "thought-leadership, conversational",
    hashtags: list[str] | None = None,
    compliance_note: str = "",
) -> str:
    return LINKEDIN_SYSTEM_PROMPT.format(
        max_length=max_length,
        tone=tone,
        hashtags=", ".join(hashtags or ["#PhysicalAI", "#Robotics", "#AI"]),
        compliance_note=compliance_note or "No disclaimers needed.",
    )


def build_user_prompt(
    platform: str,
    trends: list[dict] | None = None,
    sources: list[dict] | None = None,
    additional_context: str = "",
) -> str:
    # Trends section
    if trends:
        trend_lines = []
        for t in trends[:5]:
            line = f"- {t.get('title', '')}"
            if t.get("summary"):
                line += f": {t['summary'][:200]}"
            trend_lines.append(line)
        trends_section = "Recent trending topics:\n" + "\n".join(trend_lines)
    else:
        trends_section = "No specific trends available — write about a general Physical AI topic."

    # Sources section
    if sources:
        source_lines = []
        for s in sources[:3]:
            content = s.get("content", "")[:500]
            title = s.get("title", "Source")
            source_lines.append(f"--- {title} ---\n{content}")
        sources_section = "Reference material:\n" + "\n\n".join(source_lines)
    else:
        sources_section = ""

    return USER_PROMPT_TEMPLATE.format(
        platform=platform,
        trends_section=trends_section,
        sources_section=sources_section,
        additional_context=additional_context,
    ).strip()


def build_regen_prompt(original_content: str, new_tone: str, platform: str) -> str:
    """Build a prompt for regenerating content with a new tone."""
    return (
        f"Rewrite the following {platform} post with a '{new_tone}' tone. "
        f"Keep the same core message and facts but adjust the style.\n\n"
        f"Original:\n{original_content}\n\n"
        f"Rewrite it now. Output ONLY the rewritten text, nothing else."
    )
