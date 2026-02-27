"""Platform-specific prompt templates for content generation."""

from __future__ import annotations


TWEET_SYSTEM_PROMPT = """\
You are an expert social media strategist specializing in Physical AI and Robotics content.
You create concise, engaging tweets that drive engagement in the tech community.

Guidelines:
- Write exactly ONE tweet
- {length_note}
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

{previous_drafts_section}

{url_instruction}

{additional_context}"""


def build_tweet_system_prompt(
    max_length: int = 4000,
    tone: str = "informative, thought-provoking, professional",
    hashtags: list[str] | None = None,
    compliance_note: str = "",
    is_rewrite: bool = False,
) -> str:
    if is_rewrite:
        length_note = (
            "Length is flexible — focus on delivering value over matching the original length"
        )
    else:
        length_note = (
            f"X/Twitter supports long-form posts up to {max_length} characters. "
            f"Aim for 200-600 characters for maximum engagement, but go longer when the content warrants depth"
        )
    return TWEET_SYSTEM_PROMPT.format(
        length_note=length_note,
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
    previous_drafts: list[str] | None = None,
) -> str:
    # Trends section (with URLs)
    if trends:
        trend_lines = []
        for t in trends[:5]:
            line = f"- {t.get('title', '')}"
            if t.get("summary"):
                line += f": {t['summary'][:200]}"
            if t.get("url"):
                line += f" ({t['url']})"
            trend_lines.append(line)
        trends_section = "Recent trending topics:\n" + "\n".join(trend_lines)
    else:
        trends_section = "No specific trends available — write about a general Physical AI topic."

    # Sources section (with source paths/URLs)
    if sources:
        source_lines = []
        for s in sources[:3]:
            content = s.get("content", "")[:500]
            title = s.get("title", "Source")
            source_path = s.get("source_path", "")
            if source_path:
                source_lines.append(f"--- {title} (source: {source_path}) ---\n{content}")
            else:
                source_lines.append(f"--- {title} ---\n{content}")
        sources_section = "Reference material:\n" + "\n\n".join(source_lines)
    else:
        sources_section = (
            "Note: No reference documents available. Content will be based on trends "
            "and general knowledge only. For richer, more specific posts, add source "
            "documents via 'social-plugin fetch-sources'."
        )

    # Previous drafts section
    if previous_drafts:
        drafts_list = "\n".join(f"- {d[:150]}" for d in previous_drafts)
        previous_drafts_section = (
            "You have already generated the following posts today. "
            "Create something SUBSTANTIALLY different — different angle, different hook, "
            "different structure:\n" + drafts_list
        )
    else:
        previous_drafts_section = ""

    # URL instruction
    if platform.lower() in ("twitter", "x"):
        url_instruction = (
            "If you reference a specific article or study, include the source URL in the post."
        )
    elif platform.lower() == "linkedin":
        url_instruction = (
            "When referencing specific articles or research, include source URLs as "
            "clickable links in the post."
        )
    else:
        url_instruction = ""

    return USER_PROMPT_TEMPLATE.format(
        platform=platform,
        trends_section=trends_section,
        sources_section=sources_section,
        previous_drafts_section=previous_drafts_section,
        url_instruction=url_instruction,
        additional_context=additional_context,
    ).strip()


def build_regen_prompt(original_content: str, new_tone: str, platform: str) -> str:
    """Build a prompt for regenerating content with a new tone."""
    return (
        f"Rewrite the following {platform} post with a '{new_tone}' tone. "
        f"Feel free to restructure, rephrase, and approach the topic from a different angle. "
        f"The result should feel like a genuinely different post, not a minor rewording.\n\n"
        f"Original:\n{original_content}\n\n"
        f"Rewrite it now. Output ONLY the rewritten text, nothing else."
    )


def build_add_context_prompt(original_content: str, additional_info: str, platform: str) -> str:
    """Build a prompt for rewriting content with additional context."""
    return (
        f"Here is an existing {platform} post:\n\n"
        f"{original_content}\n\n"
        f"Rewrite it to incorporate this new information: {additional_info}\n\n"
        f"IMPORTANT: Do NOT simply append the new info. Substantially rewrite the post — "
        f"restructure it, change the hook, and weave the new information throughout. "
        f"The result should read as a fresh post, not an edited version of the original.\n\n"
        f"Output ONLY the rewritten text, nothing else."
    )
