"""LinkedIn API authentication (placeholder for future auto-posting)."""

from __future__ import annotations

import os

from social_plugin.utils.logger import get_logger

logger = get_logger()


def get_linkedin_access_token() -> str | None:
    """Get LinkedIn access token from environment."""
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    if not token:
        logger.warning("LinkedIn access token not configured — manual posting mode")
        return None
    return token


def verify_linkedin_credentials() -> dict | None:
    """Verify LinkedIn credentials. Returns None if not configured."""
    token = get_linkedin_access_token()
    if not token:
        return None

    # Placeholder — would call LinkedIn API /v2/userinfo
    logger.info("LinkedIn token present (auto-post not yet implemented)")
    return {"status": "token_present", "auto_post": False}
