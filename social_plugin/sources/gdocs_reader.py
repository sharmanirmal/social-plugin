"""Read Google Docs by direct link or document ID."""

from __future__ import annotations

import re

from social_plugin.auth.google_auth import get_docs_service
from social_plugin.db import Database
from social_plugin.sources.models import SourceDocument
from social_plugin.utils.logger import get_logger
from social_plugin.utils.retry import with_retry

logger = get_logger()

DOC_ID_PATTERN = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")


def extract_doc_id(url_or_id: str) -> str:
    """Extract Google Doc ID from a URL or return as-is if already an ID."""
    match = DOC_ID_PATTERN.search(url_or_id)
    if match:
        return match.group(1)
    # Assume it's already a doc ID
    return url_or_id


def _extract_text(doc: dict) -> str:
    """Extract plain text from Google Docs API response body."""
    body = doc.get("body", {})
    content = body.get("content", [])
    text_parts: list[str] = []

    for element in content:
        paragraph = element.get("paragraph")
        if paragraph:
            for pe in paragraph.get("elements", []):
                text_run = pe.get("textRun")
                if text_run:
                    text_parts.append(text_run.get("content", ""))

    return "".join(text_parts).strip()


class GoogleDocsReader:
    """Read content from Google Docs."""

    def __init__(self, db: Database):
        self.db = db
        self._service = None

    @property
    def service(self):
        if self._service is None:
            self._service = get_docs_service()
        return self._service

    @with_retry(max_attempts=3, retry_on=(Exception,))
    def _fetch_doc(self, doc_id: str) -> dict:
        """Fetch a Google Doc by ID."""
        return self.service.documents().get(documentId=doc_id).execute()

    def read(self, url_or_id: str, name: str = "") -> SourceDocument:
        """Read a Google Doc and return as SourceDocument."""
        doc_id = extract_doc_id(url_or_id)
        logger.info("Reading Google Doc: %s", doc_id)

        doc = self._fetch_doc(doc_id)
        title = doc.get("title", name or doc_id)
        text = _extract_text(doc)

        source = SourceDocument(
            source_type="google_doc",
            source_path=url_or_id,
            title=title,
            content=text,
        )
        source.compute_hash()

        # Check if content has changed
        existing = self.db.get_source_document_by_path(url_or_id)
        if existing and existing["content_hash"] == source.content_hash:
            logger.info("Google Doc %s unchanged, skipping", title)
            return SourceDocument.from_db_row(existing)

        self.db.insert_source_document(source.to_db_dict())
        logger.info("Stored Google Doc: %s (%d chars)", title, len(text))
        return source

    def read_all(self, config_sources: list[dict]) -> list[SourceDocument]:
        """Read all Google Docs from config."""
        docs: list[SourceDocument] = []
        for src in config_sources:
            url_or_id = src.get("url") or src.get("id", "")
            name = src.get("name", "")
            if not url_or_id:
                continue
            try:
                doc = self.read(url_or_id, name)
                docs.append(doc)
            except Exception as e:
                logger.error("Failed to read Google Doc %s: %s", url_or_id, e)
        return docs
