"""Google API authentication via service account."""

from __future__ import annotations

import os
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

from social_plugin.utils.logger import get_logger

logger = get_logger()

SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def get_google_credentials(service_account_path: str | None = None):
    """Load Google service account credentials."""
    path = service_account_path or os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH")
    if not path:
        raise ValueError(
            "Google service account path not configured. "
            "Set GOOGLE_SERVICE_ACCOUNT_PATH env var or provide path in config."
        )
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Service account file not found: {path}")

    credentials = service_account.Credentials.from_service_account_file(
        str(path), scopes=SCOPES
    )
    logger.info("Loaded Google credentials from %s", path)
    return credentials


def get_docs_service(credentials=None):
    """Get Google Docs API service."""
    if credentials is None:
        credentials = get_google_credentials()
    return build("docs", "v1", credentials=credentials, cache_discovery=False)


def get_drive_service(credentials=None):
    """Get Google Drive API service."""
    if credentials is None:
        credentials = get_google_credentials()
    return build("drive", "v3", credentials=credentials, cache_discovery=False)
