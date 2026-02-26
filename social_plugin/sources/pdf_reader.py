"""Read PDFs from local paths or remote URLs."""

from __future__ import annotations

from pathlib import Path
import tempfile

import httpx
import pdfplumber

from social_plugin.db import Database
from social_plugin.sources.models import SourceDocument
from social_plugin.utils.logger import get_logger
from social_plugin.utils.retry import with_retry

logger = get_logger()


class PDFReader:
    """Read content from PDF files (local or remote)."""

    def __init__(self, db: Database, cache_dir: str = "data/cache"):
        self.db = db
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _extract_text(self, pdf_path: str | Path) -> str:
        """Extract text from a PDF file."""
        text_parts: list[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n\n".join(text_parts)

    @with_retry(max_attempts=3, retry_on=(httpx.HTTPError, ConnectionError))
    def _download_pdf(self, url: str) -> Path:
        """Download a PDF from URL to cache directory."""
        response = httpx.get(url, timeout=60, follow_redirects=True)
        response.raise_for_status()

        # Generate cache filename from URL
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        cache_path = self.cache_dir / f"{url_hash}.pdf"
        cache_path.write_bytes(response.content)
        logger.info("Downloaded PDF to %s", cache_path)
        return cache_path

    def read(self, path_or_url: str, name: str = "") -> SourceDocument:
        """Read a PDF from local path or URL."""
        logger.info("Reading PDF: %s", path_or_url)

        if path_or_url.startswith(("http://", "https://")):
            local_path = self._download_pdf(path_or_url)
        else:
            local_path = Path(path_or_url)
            if not local_path.exists():
                raise FileNotFoundError(f"PDF not found: {local_path}")

        text = self._extract_text(local_path)
        title = name or local_path.stem

        source = SourceDocument(
            source_type="pdf",
            source_path=path_or_url,
            title=title,
            content=text,
        )
        source.compute_hash()

        existing = self.db.get_source_document_by_path(path_or_url)
        if existing and existing["content_hash"] == source.content_hash:
            logger.info("PDF %s unchanged, skipping", title)
            return SourceDocument.from_db_row(existing)

        self.db.insert_source_document(source.to_db_dict())
        logger.info("Stored PDF: %s (%d chars)", title, len(text))
        return source

    def read_all(self, config_sources: list[dict]) -> list[SourceDocument]:
        """Read all PDFs from config."""
        docs: list[SourceDocument] = []
        for src in config_sources:
            path_or_url = src.get("path") or src.get("url", "")
            name = src.get("name", "")
            if not path_or_url:
                continue
            try:
                doc = self.read(path_or_url, name)
                docs.append(doc)
            except Exception as e:
                logger.error("Failed to read PDF %s: %s", path_or_url, e)
        return docs
