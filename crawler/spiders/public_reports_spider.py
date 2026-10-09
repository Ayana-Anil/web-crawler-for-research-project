"""
public_reports_spider.py — Main Crawl Spider
==============================================

This spider:
  1. Starts from the URLs listed in settings.START_URLS.
  2. Requests each page and extracts text from HTML pages.
  3. Follows links within settings.ALLOWED_DOMAINS.
  4. Detects PDF links and downloads + extracts text from PDFs.
  5. Yields CrawledDocumentItem for each document.
  6. Respects crawl depth, page limits, and download delays.
  7. Tracks statistics for the crawl summary.

RUNNING:
    scrapy crawl public_reports
    scrapy crawl public_reports -a max_pages=50
    scrapy crawl public_reports -a max_pages=200 -a max_depth=5

The spider does NOT perform any NLP, NER, or classification.
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import scrapy
from bs4 import BeautifulSoup

from crawler.items import CrawledDocumentItem

logger = logging.getLogger(__name__)


class PublicReportsSpider(scrapy.Spider):
    """
    Crawls public child-protection report sources.

    Configuration is read from settings.py.
    Override max_pages or max_depth via command-line arguments:
        scrapy crawl public_reports -a max_pages=50
    """

    name = "public_reports"

    def __init__(self, max_pages=None, max_depth=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._max_pages_override = int(max_pages) if max_pages else None
        self._max_depth_override = int(max_depth) if max_depth else None

        # Crawl statistics (used by pipelines for the summary)
        self.crawler_stats = {
            "pages_visited": 0,
            "documents_collected": 0,
            "html_collected": 0,
            "pdf_collected": 0,
            "duplicates_skipped": 0,
            "filtered_irrelevant": 0,
            "errors": 0,
        }

        # URL deduplication set
        self._visited_urls = set()

    # ------------------------------------------------------------------
    # Spider setup
    # ------------------------------------------------------------------

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        """Create spider and set allowed_domains early for OffsiteMiddleware."""
        spider = super().from_crawler(crawler, *args, **kwargs)
        # OffsiteMiddleware reads allowed_domains at spider_opened time,
        # which is before start_requests runs.  We must set it here.
        spider.allowed_domains = crawler.settings.getlist("ALLOWED_DOMAINS", [])
        return spider

    @classmethod
    def update_settings(cls, settings):
        """Apply command-line overrides and ensure depth limit is set."""
        super().update_settings(settings)
        # Depth limit is read from our custom DEPTH_LIMIT setting
        depth = settings.getint("DEPTH_LIMIT", 3)
        settings.set("DEPTH_LIMIT", depth, priority="spider")

    async def start(self):
        """Async entry point for Scrapy 2.13+. Replaces start_requests()."""
        start_urls = self.settings.getlist("START_URLS", [])

        # Apply command-line overrides
        if self._max_pages_override is not None:
            self.settings.set("MAX_PAGES", self._max_pages_override, priority="cmdline")
        if self._max_depth_override is not None:
            self.settings.set("DEPTH_LIMIT", self._max_depth_override, priority="cmdline")

        if not start_urls:
            logger.error(
                "No START_URLS configured!  Edit crawler/settings.py "
                "and add your approved starting URLs."
            )
            return

        logger.info("Starting crawl with %d URL(s).", len(start_urls))
        logger.info("Allowed domains: %s", self.allowed_domains)
        logger.info(
            "Limits: max_pages=%s, depth=%s",
            self.settings.getint("MAX_PAGES", 100),
            self.settings.getint("DEPTH_LIMIT", 3),
        )

        for url in start_urls:
            url = url.strip()
            if url:
                yield scrapy.Request(
                    url,
                    callback=self.parse,
                    errback=self.handle_error,
                    dont_filter=True,
                )

    # ------------------------------------------------------------------
    # Main parse callback
    # ------------------------------------------------------------------

    def parse(self, response):
        """
        Process an HTTP response.

        - If the response is a PDF → extract text from PDF bytes.
        - If the response is HTML → extract text and follow links.
        """
        url = response.url

        # --- Page limit check ---
        max_pages = self.settings.getint("MAX_PAGES", 100)
        if max_pages > 0 and self.crawler_stats["pages_visited"] >= max_pages:
            logger.info("MAX_PAGES (%d) reached. Stopping.", max_pages)
            return

        # --- URL deduplication ---
        normalized = self._normalize_url(url)
        if normalized in self._visited_urls:
            logger.debug("DUPLICATE URL skipped: %s", url)
            return
        self._visited_urls.add(normalized)
        self.crawler_stats["pages_visited"] += 1

        logger.info("VISITING [%d]: %s", self.crawler_stats["pages_visited"], url)

        # --- Determine content type ---
        content_type = response.headers.get("Content-Type", b"").decode("utf-8", errors="ignore").lower()

        if url.lower().endswith(".pdf") or "application/pdf" in content_type:
            yield from self._handle_pdf(response)
        elif "text/html" in content_type or not content_type:
            yield from self._handle_html(response)
        else:
            logger.debug("Skipping unsupported content type (%s): %s", content_type, url)

    # ------------------------------------------------------------------
    # HTML handling
    # ------------------------------------------------------------------

    def _handle_html(self, response):
        """Extract text from an HTML page and follow links."""
        try:
            text = self._extract_text_from_html(response)
            title = self._extract_title(response)
        except Exception as exc:
            logger.warning("HTML PARSE ERROR for %s: %s", response.url, exc)
            self.crawler_stats["errors"] += 1
            return

        if not text or len(text.strip()) < 50:
            logger.debug("Skipping page with too little text: %s", response.url)
        else:
            item = CrawledDocumentItem()
            item["source_url"] = response.url
            item["title"] = title
            item["document_type"] = "html"
            item["text"] = text
            item["content_hash"] = self._compute_hash(text)
            item["domain"] = urlparse(response.url).netloc
            item["collection_timestamp"] = datetime.now(timezone.utc).isoformat()
            item["publication_date"] = self._try_extract_date(response)
            yield item

        # --- Follow links ---
        yield from self._follow_links(response)

    def _extract_text_from_html(self, response):
        """
        Extract meaningful text content from an HTML page.

        Removes:
        - <script> and <style> elements
        - Navigation (<nav>), header, footer elements
        - Form elements
        - All HTML tags

        Keeps:
        - Headings, paragraphs, article text, list items
        - The page's actual readable content
        """
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove elements that are not document content
        for tag in soup.find_all([
            "script", "style", "noscript",
            "nav", "header", "footer",
            "form", "iframe", "svg",
            "button", "input", "select", "textarea",
        ]):
            tag.decompose()

        # Remove common boilerplate by class/id patterns
        boilerplate_patterns = re.compile(
            r"(cookie|consent|popup|modal|sidebar|widget|ad-|advert|"
            r"social-share|share-button|breadcrumb|pagination|"
            r"skip-to|screen-reader)",
            re.IGNORECASE,
        )
        for tag in soup.find_all(
            attrs={"class": boilerplate_patterns}
        ):
            tag.decompose()
        for tag in soup.find_all(
            attrs={"id": boilerplate_patterns}
        ):
            tag.decompose()

        # Try to find the main content area first
        main_content = (
            soup.find("main")
            or soup.find(attrs={"role": "main"})
            or soup.find(id=re.compile(r"^content$|^main$", re.IGNORECASE))
            or soup.find(class_=re.compile(r"main-content|site-content|page-content|content-area", re.IGNORECASE))
        )

        target = main_content if main_content else soup.body if soup.body else soup

        # Extract text from meaningful elements
        text_parts = []
        for element in target.find_all([
            "h1", "h2", "h3", "h4", "h5", "h6",
            "p", "li", "td", "th",
            "blockquote", "pre", "figcaption",
            "dt", "dd",
        ]):
            element_text = element.get_text(separator=" ", strip=True)
            if element_text:
                text_parts.append(element_text)

        # If structured extraction yielded little, fall back to full text
        full_text = "\n".join(text_parts)
        if len(full_text) < 100:
            full_text = target.get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        full_text = re.sub(r"\n{3,}", "\n\n", full_text)
        full_text = re.sub(r"[ \t]+", " ", full_text)

        return full_text.strip()

    def _extract_title(self, response):
        """Extract the page title from <title> or <h1>."""
        # Try <title> tag
        title = response.css("title::text").get()
        if title:
            title = title.strip()
            if title:
                return title

        # Try first <h1>
        h1 = response.css("h1::text").get()
        if h1:
            return h1.strip()

        return None

    def _try_extract_date(self, response):
        """
        Try to extract a publication date from common meta tags.
        Returns the date string if found, None otherwise.
        Does NOT infer or guess dates.
        """
        # Common meta tags for publication dates
        date_meta_names = [
            "article:published_time",
            "datePublished",
            "date",
            "DC.date",
            "DC.date.issued",
            "publication_date",
            "publish-date",
        ]

        for name in date_meta_names:
            # Try property attribute
            content = response.css(
                f'meta[property="{name}"]::attr(content)'
            ).get()
            if content:
                return content.strip()

            # Try name attribute
            content = response.css(
                f'meta[name="{name}"]::attr(content)'
            ).get()
            if content:
                return content.strip()

        # Try <time> element with datetime attribute
        time_dt = response.css("time::attr(datetime)").get()
        if time_dt:
            return time_dt.strip()

        return None

    # ------------------------------------------------------------------
    # PDF handling
    # ------------------------------------------------------------------

    def _handle_pdf(self, response):
        """Download and extract text from a PDF response."""
        logger.info("PDF DISCOVERED: %s", response.url)

        try:
            text = self._extract_text_from_pdf(response.body)
        except Exception as exc:
            logger.warning(
                "PDF EXTRACTION FAILED for %s: %s", response.url, exc
            )
            self.crawler_stats["errors"] += 1
            return

        if not text or len(text.strip()) < 20:
            logger.info("PDF has no extractable text: %s", response.url)
            return

        # Use the PDF filename as title
        title = self._pdf_title_from_url(response.url)

        item = CrawledDocumentItem()
        item["source_url"] = response.url
        item["title"] = title
        item["document_type"] = "pdf"
        item["text"] = text
        item["content_hash"] = self._compute_hash(text)
        item["domain"] = urlparse(response.url).netloc
        item["collection_timestamp"] = datetime.now(timezone.utc).isoformat()
        item["publication_date"] = None  # Cannot reliably extract from PDF
        yield item

    def _extract_text_from_pdf(self, pdf_bytes):
        """
        Extract text from PDF bytes using PyMuPDF.

        Handles:
        - Multi-page PDFs
        - Skips encrypted/password-protected PDFs gracefully
        """
        import fitz  # PyMuPDF

        text_parts = []
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            raise RuntimeError(f"Cannot open PDF: {exc}") from exc

        if doc.is_encrypted:
            doc.close()
            raise RuntimeError("PDF is encrypted/password-protected — skipping.")

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text("text")
                if page_text:
                    text_parts.append(page_text)
        finally:
            doc.close()

        full_text = "\n\n".join(text_parts)

        # Clean up whitespace
        full_text = re.sub(r"\n{3,}", "\n\n", full_text)
        full_text = re.sub(r"[ \t]+", " ", full_text)

        return full_text.strip()

    @staticmethod
    def _pdf_title_from_url(url):
        """Extract a human-readable title from a PDF URL."""
        path = urlparse(url).path
        filename = path.rsplit("/", 1)[-1] if "/" in path else path
        if filename.lower().endswith(".pdf"):
            filename = filename[:-4]
        # Replace hyphens/underscores with spaces
        title = filename.replace("-", " ").replace("_", " ")
        return title if title else None

    # ------------------------------------------------------------------
    # Link following
    # ------------------------------------------------------------------

    def _follow_links(self, response):
        """
        Extract and follow links from the current page.

        - Follows HTML page links via self.parse callback.
        - Directly requests PDF links for PDF handling.
        - Only follows links within allowed domains.
        """
        max_pages = self.settings.getint("MAX_PAGES", 100)

        for link in response.css("a::attr(href)").getall():
            # Resolve relative URLs
            absolute_url = response.urljoin(link)

            # Skip non-HTTP(S) links
            if not absolute_url.startswith(("http://", "https://")):
                continue

            # Skip already-visited URLs
            normalized = self._normalize_url(absolute_url)
            if normalized in self._visited_urls:
                continue

            # Skip fragment-only links to same page
            parsed = urlparse(absolute_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            current_base = urlparse(response.url)
            current_base_url = f"{current_base.scheme}://{current_base.netloc}{current_base.path}"
            if base_url == current_base_url and parsed.fragment:
                continue

            # Skip obviously non-document links
            skip_extensions = {
                ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico",
                ".mp3", ".mp4", ".avi", ".mov", ".wmv",
                ".zip", ".tar", ".gz", ".rar",
                ".exe", ".dmg", ".msi",
                ".css", ".js",
            }
            path_lower = parsed.path.lower()
            if any(path_lower.endswith(ext) for ext in skip_extensions):
                continue

            # Check page limit
            if max_pages > 0 and self.crawler_stats["pages_visited"] >= max_pages:
                return

            # PDF links get PDF handling
            if path_lower.endswith(".pdf"):
                yield scrapy.Request(
                    absolute_url,
                    callback=self.parse,
                    errback=self.handle_error,
                    dont_filter=False,
                )
            else:
                yield scrapy.Request(
                    absolute_url,
                    callback=self.parse,
                    errback=self.handle_error,
                    dont_filter=False,
                )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_url(url):
        """
        Normalize a URL for deduplication:
        - Remove fragment (#section)
        - Remove trailing slash
        - Lowercase scheme and host
        """
        parsed = urlparse(url)
        normalized = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        normalized = normalized.rstrip("/")
        return normalized

    @staticmethod
    def _compute_hash(text):
        """Compute SHA-256 hash of the text for content deduplication."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def handle_error(self, failure):
        """
        Handle request failures (timeouts, DNS errors, HTTP errors, etc.).
        Logs the error and allows the crawl to continue.
        """
        request = failure.request
        self.crawler_stats["errors"] += 1

        if failure.check(scrapy.spidermiddlewares.httperror.HttpError):
            response = failure.value.response
            logger.warning(
                "HTTP ERROR %d: %s", response.status, request.url
            )
        elif failure.check(Exception):
            logger.warning(
                "REQUEST FAILED for %s: %s",
                request.url,
                failure.getErrorMessage(),
            )
        else:
            logger.warning(
                "UNKNOWN ERROR for %s: %s",
                request.url,
                repr(failure),
            )
