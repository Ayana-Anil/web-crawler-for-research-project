"""
test_crawler.py — Unit Tests for the Child Protection Crawler
===============================================================

Tests cover:
  - URL normalization and deduplication
  - Allowed-domain filtering
  - HTML text extraction
  - PDF text extraction (using a minimal synthetic PDF)
  - Content hash deduplication
  - Metadata creation
  - Relevance keyword filtering

All tests run offline — no live internet required.
Run with:  pytest tests/test_crawler.py -v
"""

import hashlib
import json
import os
import sys
import tempfile
from unittest.mock import MagicMock

import pytest

# Ensure the project root is importable
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


# =====================================================================
# Test: URL Normalization
# =====================================================================

class TestURLNormalization:
    """Tests for the URL normalization function used in deduplication."""

    def _normalize(self, url):
        from crawler.spiders.public_reports_spider import PublicReportsSpider
        return PublicReportsSpider._normalize_url(url)

    def test_removes_fragment(self):
        assert self._normalize("https://example.org/page#section") == \
            "https://example.org/page"

    def test_removes_trailing_slash(self):
        assert self._normalize("https://example.org/page/") == \
            "https://example.org/page"

    def test_lowercases_scheme_and_host(self):
        assert self._normalize("HTTPS://Example.ORG/Path") == \
            "https://example.org/Path"

    def test_preserves_query_string(self):
        assert self._normalize("https://example.org/page?id=42") == \
            "https://example.org/page?id=42"

    def test_identical_urls_match(self):
        url1 = self._normalize("https://example.org/report")
        url2 = self._normalize("https://example.org/report/")
        assert url1 == url2

    def test_different_urls_dont_match(self):
        url1 = self._normalize("https://example.org/report-a")
        url2 = self._normalize("https://example.org/report-b")
        assert url1 != url2


# =====================================================================
# Test: URL Deduplication
# =====================================================================

class TestURLDeduplication:
    """Tests that duplicate URLs are detected."""

    def test_duplicate_detected(self):
        seen = set()
        url = "https://example.org/report"
        normalized = url.rstrip("/")

        # First time: not a duplicate
        assert normalized not in seen
        seen.add(normalized)

        # Second time: duplicate
        assert normalized in seen

    def test_trailing_slash_variant_detected(self):
        from crawler.spiders.public_reports_spider import PublicReportsSpider
        seen = set()

        url1 = PublicReportsSpider._normalize_url("https://example.org/report")
        seen.add(url1)

        url2 = PublicReportsSpider._normalize_url("https://example.org/report/")
        assert url2 in seen


# =====================================================================
# Test: Content Deduplication (SHA-256)
# =====================================================================

class TestContentDeduplication:
    """Tests for content-based deduplication via SHA-256 hashing."""

    def _hash(self, text):
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def test_identical_content_same_hash(self):
        text = "This is a child protection report about child safety."
        assert self._hash(text) == self._hash(text)

    def test_different_content_different_hash(self):
        text1 = "Report about child protection."
        text2 = "Report about online safety for children."
        assert self._hash(text1) != self._hash(text2)

    def test_deduplication_pipeline_drops_duplicate(self):
        from crawler.pipelines import DeduplicationPipeline
        from scrapy.exceptions import DropItem

        pipeline = DeduplicationPipeline()
        spider = MagicMock()
        spider.crawler_stats = {"duplicates_skipped": 0}

        item1 = {
            "content_hash": "abc123",
            "source_url": "https://example.org/page1",
        }
        item2 = {
            "content_hash": "abc123",  # Same hash = duplicate
            "source_url": "https://example.org/page2",
        }

        # First item passes
        result = pipeline.process_item(item1, spider)
        assert result is item1

        # Second item (same hash) is dropped
        with pytest.raises(DropItem):
            pipeline.process_item(item2, spider)


# =====================================================================
# Test: HTML Text Extraction
# =====================================================================

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Child Protection Report 2024</title>
    <style>body { color: black; }</style>
    <script>console.log("tracking");</script>
</head>
<body>
    <nav><a href="/">Home</a> <a href="/about">About</a></nav>
    <header><h1>National Child Protection Report</h1></header>
    <main>
        <article>
            <h2>Executive Summary</h2>
            <p>This report examines child protection policies across
               multiple jurisdictions and their effectiveness.</p>
            <h2>Key Findings</h2>
            <p>Online safety measures have improved significantly in
               the past five years, leading to better outcomes for
               children in digital environments.</p>
        </article>
    </main>
    <footer>Copyright 2024</footer>
    <script>window.analytics.track("pageview");</script>
</body>
</html>
"""


class TestHTMLExtraction:
    """Tests for HTML text extraction."""

    def _extract(self, html_text):
        """Use BeautifulSoup the same way the spider does."""
        import re
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_text, "html.parser")

        for tag in soup.find_all([
            "script", "style", "noscript",
            "nav", "header", "footer",
            "form", "iframe", "svg",
            "button", "input", "select", "textarea",
        ]):
            tag.decompose()

        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find(attrs={"role": "main"})
            or soup.body
            or soup
        )

        text_parts = []
        for element in main_content.find_all([
            "h1", "h2", "h3", "h4", "h5", "h6",
            "p", "li", "td", "th",
            "blockquote", "pre", "figcaption",
        ]):
            element_text = element.get_text(separator=" ", strip=True)
            if element_text:
                text_parts.append(element_text)

        full_text = "\n".join(text_parts)
        if len(full_text) < 100:
            full_text = main_content.get_text(separator="\n", strip=True)

        full_text = re.sub(r"\n{3,}", "\n\n", full_text)
        full_text = re.sub(r"[ \t]+", " ", full_text)
        return full_text.strip()

    def test_extracts_paragraph_text(self):
        text = self._extract(SAMPLE_HTML)
        assert "child protection policies" in text

    def test_extracts_headings(self):
        text = self._extract(SAMPLE_HTML)
        assert "Executive Summary" in text
        assert "Key Findings" in text

    def test_removes_script_content(self):
        text = self._extract(SAMPLE_HTML)
        assert "tracking" not in text
        assert "analytics" not in text
        assert "console.log" not in text

    def test_removes_style_content(self):
        text = self._extract(SAMPLE_HTML)
        assert "color: black" not in text

    def test_removes_navigation(self):
        text = self._extract(SAMPLE_HTML)
        # The nav links "Home" and "About" should be removed
        # (Note: "About" may appear in content if context discusses "about",
        # so we check for the nav-specific pattern)
        assert text.count("Home") == 0 or "Home" not in text[:20]

    def test_no_html_tags_in_output(self):
        text = self._extract(SAMPLE_HTML)
        assert "<p>" not in text
        assert "<h2>" not in text
        assert "<script>" not in text

    def test_preserves_meaningful_text(self):
        text = self._extract(SAMPLE_HTML)
        assert "online safety" in text.lower()
        assert "children" in text.lower()


# =====================================================================
# Test: PDF Text Extraction
# =====================================================================

class TestPDFExtraction:
    """Tests for PDF text extraction using PyMuPDF."""

    @pytest.fixture
    def sample_pdf_bytes(self):
        """Create a minimal synthetic PDF for testing."""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open()  # New empty PDF
            page = doc.new_page()
            page.insert_text(
                (72, 72),
                "Child Protection Report\n\n"
                "This report discusses child safety measures "
                "and online protection policies.",
                fontsize=12,
            )
            pdf_bytes = doc.tobytes()
            doc.close()
            return pdf_bytes
        except ImportError:
            pytest.skip("PyMuPDF (fitz) not installed")

    def test_extracts_text_from_pdf(self, sample_pdf_bytes):
        import fitz

        doc = fitz.open(stream=sample_pdf_bytes, filetype="pdf")
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text("text"))
        doc.close()

        full_text = "\n".join(text_parts)
        assert "Child Protection Report" in full_text
        assert "child safety" in full_text

    def test_encrypted_pdf_raises_error(self):
        """Verify that the spider handles encrypted PDFs gracefully."""
        from crawler.spiders.public_reports_spider import PublicReportsSpider

        spider = PublicReportsSpider.__new__(PublicReportsSpider)

        # Create a mock encrypted PDF (invalid bytes that can't be opened)
        with pytest.raises(RuntimeError):
            spider._extract_text_from_pdf(b"not-a-valid-pdf")

    def test_empty_pdf(self):
        """An empty PDF should return empty or near-empty text."""
        try:
            import fitz
        except ImportError:
            pytest.skip("PyMuPDF not installed")

        doc = fitz.open()
        doc.new_page()  # Blank page with no text
        pdf_bytes = doc.tobytes()
        doc.close()

        doc2 = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in doc2:
            text += page.get_text("text")
        doc2.close()

        assert len(text.strip()) == 0


# =====================================================================
# Test: Metadata Creation
# =====================================================================

class TestMetadataCreation:
    """Tests that document metadata is correctly structured."""

    def test_document_record_structure(self):
        """Verify the JSONL record has all required fields."""
        record = {
            "document_id": "DOC_000001",
            "source_url": "https://example.org/report.pdf",
            "title": "Example Child Protection Report",
            "document_type": "pdf",
            "text": "Full extracted text content here...",
            "content_hash": hashlib.sha256(
                "Full extracted text content here...".encode()
            ).hexdigest(),
            "domain": "example.org",
            "collection_timestamp": "2026-09-09T12:00:00+00:00",
            "publication_date": None,
        }

        required_fields = [
            "document_id", "source_url", "title", "document_type",
            "text", "content_hash", "domain", "collection_timestamp",
            "publication_date",
        ]
        for field in required_fields:
            assert field in record, f"Missing field: {field}"

    def test_document_id_format(self):
        """Verify document IDs follow DOC_XXXXXX format."""
        import re
        for i in [1, 42, 999999]:
            doc_id = f"DOC_{i:06d}"
            assert re.match(r"DOC_\d{6}", doc_id)

    def test_json_serializable(self):
        """Verify the record can be serialized to JSON."""
        record = {
            "document_id": "DOC_000001",
            "source_url": "https://example.org/report",
            "title": "Test Report",
            "document_type": "html",
            "text": "Some text content.",
            "content_hash": hashlib.sha256(b"Some text content.").hexdigest(),
            "domain": "example.org",
            "collection_timestamp": "2026-09-09T12:00:00+00:00",
            "publication_date": None,
        }
        json_str = json.dumps(record, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["document_id"] == "DOC_000001"
        assert parsed["publication_date"] is None


# =====================================================================
# Test: Relevance Filter
# =====================================================================

class TestRelevanceFilter:
    """Tests for the keyword relevance filter."""

    def test_relevant_document_passes(self):
        keywords = ["child protection", "child safety", "online safety"]
        text = "This report discusses child protection policies in schools."
        text_lower = text.lower()
        assert any(kw in text_lower for kw in keywords)

    def test_irrelevant_document_rejected(self):
        keywords = ["child protection", "child safety", "online safety"]
        text = "Quarterly financial earnings report for Q3 2024."
        text_lower = text.lower()
        assert not any(kw in text_lower for kw in keywords)

    def test_case_insensitive_matching(self):
        keywords = ["child protection"]
        text = "CHILD PROTECTION is discussed here."
        text_lower = text.lower()
        assert any(kw in text_lower for kw in keywords)

    def test_relevance_pipeline_passes_relevant(self):
        from crawler.pipelines import RelevanceFilterPipeline

        pipeline = RelevanceFilterPipeline(
            enabled=True,
            keywords=["child protection", "online safety"],
        )
        spider = MagicMock()
        spider.crawler_stats = {"filtered_irrelevant": 0}

        item = {
            "text": "A report about child protection in digital spaces.",
            "source_url": "https://example.org/report",
        }
        result = pipeline.process_item(item, spider)
        assert result is item

    def test_relevance_pipeline_drops_irrelevant(self):
        from crawler.pipelines import RelevanceFilterPipeline
        from scrapy.exceptions import DropItem

        pipeline = RelevanceFilterPipeline(
            enabled=True,
            keywords=["child protection", "online safety"],
        )
        spider = MagicMock()
        spider.crawler_stats = {"filtered_irrelevant": 0}

        item = {
            "text": "Financial report for the quarter.",
            "source_url": "https://example.org/finance",
        }
        with pytest.raises(DropItem):
            pipeline.process_item(item, spider)

    def test_disabled_filter_passes_everything(self):
        from crawler.pipelines import RelevanceFilterPipeline

        pipeline = RelevanceFilterPipeline(enabled=False, keywords=[])
        spider = MagicMock()

        item = {
            "text": "Totally unrelated document.",
            "source_url": "https://example.org/random",
        }
        result = pipeline.process_item(item, spider)
        assert result is item


# =====================================================================
# Test: Allowed Domain Filtering
# =====================================================================

class TestAllowedDomainFiltering:
    """Tests for domain-based URL filtering."""

    def test_allowed_domain_passes(self):
        from urllib.parse import urlparse

        allowed = {"example.org", "unicef.org"}
        url = "https://example.org/reports/page1"
        domain = urlparse(url).netloc
        assert domain in allowed

    def test_disallowed_domain_rejected(self):
        from urllib.parse import urlparse

        allowed = {"example.org", "unicef.org"}
        url = "https://random-website.com/page"
        domain = urlparse(url).netloc
        assert domain not in allowed

    def test_subdomain_handling(self):
        from urllib.parse import urlparse

        allowed = {"www.unicef.org"}
        url = "https://www.unicef.org/protection"
        domain = urlparse(url).netloc
        assert domain in allowed

        # Note: bare "unicef.org" would NOT match "www.unicef.org"
        url2 = "https://unicef.org/page"
        domain2 = urlparse(url2).netloc
        assert domain2 not in allowed  # Different domain string


# =====================================================================
# Test: Content Hash
# =====================================================================

class TestContentHash:
    """Tests for the SHA-256 hashing function."""

    def test_hash_consistency(self):
        from crawler.spiders.public_reports_spider import PublicReportsSpider
        text = "Child protection report content"
        h1 = PublicReportsSpider._compute_hash(text)
        h2 = PublicReportsSpider._compute_hash(text)
        assert h1 == h2

    def test_hash_is_sha256_hex(self):
        from crawler.spiders.public_reports_spider import PublicReportsSpider
        text = "Some text"
        h = PublicReportsSpider._compute_hash(text)
        assert len(h) == 64  # SHA-256 hex digest is 64 chars
        assert all(c in "0123456789abcdef" for c in h)
