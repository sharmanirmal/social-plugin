"""Retry utilities using tenacity."""

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging

logger = logging.getLogger("social_plugin")


def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1,
    max_wait: float = 30,
    retry_on: tuple[type[Exception], ...] = (Exception,),
):
    """Decorator factory for retrying operations with exponential backoff."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(retry_on),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
