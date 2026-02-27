"""Platform-specific prompt templates for content generation."""

from __future__ import annotations


TWEET_SYSTEM_PROMPT = """\
You are an expert social media strategist specializing in {topic} content.
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

{rules_section}\
Output ONLY the tweet text, nothing else. No quotes, no labels, no explanations."""


LINKEDIN_SYSTEM_PROMPT = """\
You are an expert social media strategist specializing in {topic} content.
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

{rules_section}\
Output ONLY the post text, nothing else. No quotes, no labels, no explanations."""


USER_PROMPT_TEMPLATE = """\
Create a {platform} post about {topic}.

{trends_section}

{sources_section}

{style_section}

{previous_drafts_section}

{rejection_section}

{approval_section}

{url_instruction}

{additional_context}"""


def build_rules_section(rules: dict | None = None) -> str:
    """Build a formatted rules section from DO's and DON'Ts.

    Returns a string like:
        Content rules:
        DO:
        - Include specific data points...
        DON'T:
        - Never use clickbait...

    Returns empty string if no rules provided.
    """
    if not rules:
        return ""

    do_rules = rules.get("do", [])
    dont_rules = rules.get("dont", [])

    if not do_rules and not dont_rules:
        return ""

    parts = ["Content rules:"]
    if do_rules:
        parts.append("DO:")
        for rule in do_rules:
            parts.append(f"- {rule}")
    if dont_rules:
        parts.append("DON'T:")
        for rule in dont_rules:
            parts.append(f"- {rule}")

    return "\n".join(parts) + "\n\n"


def build_tweet_system_prompt(
    max_length: int = 280,
    tone: str = "informative, thought-provoking, professional",
    hashtags: list[str] | None = None,
    compliance_note: str = "",
    is_rewrite: bool = False,
    topic: str = "Physical AI and Robotics",
    rules: dict | None = None,
) -> str:
    if is_rewrite:
        length_note = (
            "Length is flexible — focus on delivering value over matching the original length"
        )
    elif max_length <= 280:
        length_note = (
            f"Stay within {max_length} characters (including hashtags). "
            f"Be concise and impactful — every word counts"
        )
    else:
        length_note = (
            f"X/Twitter supports long-form posts up to {max_length} characters. "
            f"Aim for 200-600 characters for maximum engagement, but go longer when the content warrants depth"
        )
    return TWEET_SYSTEM_PROMPT.format(
        topic=topic,
        length_note=length_note,
        tone=tone,
        hashtags=", ".join(hashtags) if hashtags else "relevant hashtags",
        compliance_note=compliance_note or "No disclaimers needed.",
        rules_section=build_rules_section(rules),
    )


def build_linkedin_system_prompt(
    max_length: int = 3000,
    tone: str = "thought-leadership, conversational",
    hashtags: list[str] | None = None,
    compliance_note: str = "",
    topic: str = "Physical AI and Robotics",
    rules: dict | None = None,
) -> str:
    return LINKEDIN_SYSTEM_PROMPT.format(
        topic=topic,
        max_length=max_length,
        tone=tone,
        hashtags=", ".join(hashtags) if hashtags else "relevant hashtags",
        compliance_note=compliance_note or "No disclaimers needed.",
        rules_section=build_rules_section(rules),
    )


def build_user_prompt(
    platform: str,
    trends: list[dict] | None = None,
    sources: list[dict] | None = None,
    additional_context: str = "",
    previous_drafts: list[str] | None = None,
    topic: str = "Physical AI and Robotics",
    style_examples: list[str] | None = None,
    rejection_feedback: list[str] | None = None,
    approval_feedback: list[str] | None = None,
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
        trends_section = f"No specific trends available — write about a general {topic} topic."

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

    # Style examples section
    if style_examples:
        examples_text = "\n\n".join(f'Example {i+1}: "{ex}"' for i, ex in enumerate(style_examples[:3]))
        style_section = (
            "Here are examples of posts the user likes. "
            "Match this voice, structure, and style:\n\n" + examples_text
        )
    else:
        style_section = ""

    # Previous drafts section
    if previous_drafts:
        drafts_list = "\n".join(f"- {d[:150]}" for d in previous_drafts)
        previous_drafts_section = (
            "You have recently generated the following posts. "
            "Create something SUBSTANTIALLY different — different angle, different hook, "
            "different structure:\n" + drafts_list
        )
    else:
        previous_drafts_section = ""

    # Rejection feedback
    if rejection_feedback:
        feedback_lines = "\n".join(f'- "{note}"' for note in rejection_feedback)
        rejection_section = "Previous feedback — things to AVOID:\n" + feedback_lines
    else:
        rejection_section = ""

    # Approval feedback
    if approval_feedback:
        feedback_lines = "\n".join(f'- "{note}"' for note in approval_feedback)
        approval_section = "Previous feedback — things that worked WELL:\n" + feedback_lines
    else:
        approval_section = ""

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
        topic=topic,
        trends_section=trends_section,
        sources_section=sources_section,
        style_section=style_section,
        previous_drafts_section=previous_drafts_section,
        rejection_section=rejection_section,
        approval_section=approval_section,
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
