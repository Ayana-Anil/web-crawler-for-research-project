"""
items.py — Scrapy Item Definitions
====================================

Defines the data structure for each collected document.
Every document (HTML page or PDF) that the crawler collects is represented
as a CrawledDocumentItem.

Fields:
    document_id         : Unique identifier (e.g. DOC_000001)
    source_url          : The URL the document was fetched from
    title               : Page title or PDF filename
    document_type       : "html" or "pdf"
    text                : Full extracted plain text
    content_hash        : SHA-256 hash of the text (for deduplication)
    domain              : Domain name of the source URL
    collection_timestamp: ISO-8601 timestamp when the document was collected
    publication_date    : Publication date if clearly available (else None)
"""

import scrapy


class CrawledDocumentItem(scrapy.Item):
    """Represents one collected document (HTML page or PDF)."""

    document_id = scrapy.Field()
    source_url = scrapy.Field()
    title = scrapy.Field()
    document_type = scrapy.Field()           # "html" or "pdf"
    text = scrapy.Field()
    content_hash = scrapy.Field()
    domain = scrapy.Field()
    collection_timestamp = scrapy.Field()
    publication_date = scrapy.Field()        # None if not available
