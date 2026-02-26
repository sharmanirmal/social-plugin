"""Twitter/X API authentication via tweepy (pay-per-use)."""

from __future__ import annotations

import os

import tweepy

from social_plugin.utils.logger import get_logger

logger = get_logger()


def get_twitter_client() -> tweepy.Client:
    """Get authenticated Twitter API v2 client."""
    bearer_token = os.environ.get("TWITTER_BEARER_TOKEN")
    api_key = os.environ.get("TWITTER_API_KEY")
    api_secret = os.environ.get("TWITTER_API_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, access_token, access_token_secret]):
        raise ValueError(
            "Twitter credentials not fully configured. "
            "Set TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, "
            "TWITTER_ACCESS_TOKEN_SECRET in .env"
        )

    client = tweepy.Client(
        bearer_token=bearer_token,
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )
    logger.info("Twitter client initialized")
    return client


def get_twitter_api_v1() -> tweepy.API:
    """Get Twitter API v1.1 (needed for media uploads)."""
    api_key = os.environ.get("TWITTER_API_KEY")
    api_secret = os.environ.get("TWITTER_API_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
    return tweepy.API(auth)


def verify_twitter_credentials() -> dict:
    """Verify Twitter credentials are valid. Returns user info."""
    client = get_twitter_client()
    me = client.get_me()
    if me.data:
        info = {"id": me.data.id, "username": me.data.username, "name": me.data.name}
        logger.info("Twitter auth verified: @%s", info["username"])
        return info
    raise ValueError("Could not verify Twitter credentials")
