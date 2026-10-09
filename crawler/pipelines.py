"""
pipelines.py — Scrapy Item Pipelines
======================================

Three pipelines process every collected document in order:

1. DeduplicationPipeline  (priority 100)
   - Checks if the document's content_hash has been seen before.
   - Drops duplicates so we never save the same text twice.

2. RelevanceFilterPipeline (priority 200)
   - If ENABLE_RELEVANCE_FILTER is True in settings, checks whether
     the document text contains at least one of the RELEVANCE_KEYWORDS.
   - If none match, the document is dropped.
   - If the filter is disabled, all documents pass through.

3. DataStoragePipeline (priority 300)
   - Assigns a sequential document_id (DOC_000001, DOC_000002, …).
   - Appends the document as a JSON line to the JSONL output file.
   - Appends a row to the metadata CSV.
   - Logs what was saved.
"""

import csv
import json
import logging
import os
from pathlib import Path

from scrapy.exceptions import DropItem


logger = logging.getLogger(__name__)


class DeduplicationPipeline:
    """
    Drops items whose text content has already been collected.

    HOW IT WORKS:
    - Each document's text is hashed (SHA-256) by the spider before
      reaching the pipeline.  The hash is stored in item["content_hash"].
    - This pipeline keeps a set of all hashes seen so far.
    - If a new item's hash is already in the set, it is dropped as a duplicate.
    - This prevents saving two documents with identical text even if they
      came from different URLs.
    """

    def __init__(self):
        self.seen_hashes = set()

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        raw_dir = crawler.settings.get("RAW_DATA_DIR")
        jsonl_filename = crawler.settings.get("JSONL_FILENAME", "collected_documents.jsonl")
        if raw_dir:
            jsonl_path = os.path.join(raw_dir, jsonl_filename)
            if os.path.exists(jsonl_path):
                try:
                    with open(jsonl_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip():
                                data = json.loads(line)
                                if "content_hash" in data:
                                    pipeline.seen_hashes.add(data["content_hash"])
                except Exception:
                    pass
        return pipeline

    def process_item(self, item, spider):
        content_hash = item.get("content_hash")
        if content_hash in self.seen_hashes:
            logger.info(
                "DUPLICATE CONTENT skipped (hash=%s): %s",
                content_hash[:16],
                item.get("source_url", "unknown"),
            )
            spider.crawler_stats["duplicates_skipped"] += 1
            raise DropItem(f"Duplicate content: {item['source_url']}")

        self.seen_hashes.add(content_hash)
        return item


class RelevanceFilterPipeline:
    """
    Optionally filters documents by keyword relevance.

    HOW IT WORKS:
    - Reads ENABLE_RELEVANCE_FILTER and RELEVANCE_KEYWORDS from settings.
    - If enabled, converts the document text to lowercase and checks if
      ANY of the keywords appear in it.
    - If at least one keyword is found → document passes through.
    - If none are found → document is dropped.
    - If the filter is disabled → all documents pass through.

    This is a very simple substring match.  It does NOT use NLP.
    """

    def __init__(self, enabled, keywords):
        self.enabled = enabled
        self.keywords = [kw.lower() for kw in keywords]

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            enabled=crawler.settings.getbool("ENABLE_RELEVANCE_FILTER", True),
            keywords=crawler.settings.getlist("RELEVANCE_KEYWORDS", []),
        )

    def process_item(self, item, spider):
        if not self.enabled:
            return item

        text_lower = (item.get("text") or "").lower()

        for keyword in self.keywords:
            if keyword in text_lower:
                return item

        logger.info(
            "NOT RELEVANT (no keyword match): %s",
            item.get("source_url", "unknown"),
        )
        spider.crawler_stats["filtered_irrelevant"] += 1
        raise DropItem(f"Not relevant: {item['source_url']}")


class DataStoragePipeline:
    """
    Saves collected documents to JSONL and metadata CSV.

    HOW IT WORKS:
    - On spider_opened: creates output directories and opens file handles.
    - On process_item: assigns a document_id, writes one JSON line to the
      JSONL file, and appends one row to the metadata CSV.
    - On spider_closed: closes file handles and logs a summary.
    """

    def __init__(self, raw_dir, metadata_dir, jsonl_filename, csv_filename):
        self.raw_dir = raw_dir
        self.metadata_dir = metadata_dir
        self.jsonl_filename = jsonl_filename
        self.csv_filename = csv_filename
        self.jsonl_file = None
        self.csv_file = None
        self.csv_writer = None
        self.doc_counter = 0

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            raw_dir=crawler.settings.get("RAW_DATA_DIR"),
            metadata_dir=crawler.settings.get("METADATA_DIR"),
            jsonl_filename=crawler.settings.get(
                "JSONL_FILENAME", "collected_documents.jsonl"
            ),
            csv_filename=crawler.settings.get(
                "METADATA_CSV_FILENAME", "crawl_metadata.csv"
            ),
        )

    def open_spider(self, spider):
        """Create directories and open output files."""
        Path(self.raw_dir).mkdir(parents=True, exist_ok=True)
        Path(self.metadata_dir).mkdir(parents=True, exist_ok=True)

        jsonl_path = os.path.join(self.raw_dir, self.jsonl_filename)
        csv_path = os.path.join(self.metadata_dir, self.csv_filename)

        self.jsonl_file = open(jsonl_path, "a", encoding="utf-8")

        # Open CSV; write header only if file is new/empty.
        file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
        self.csv_file = open(csv_path, "a", encoding="utf-8", newline="")
        self.csv_writer = csv.writer(self.csv_file)

        if not file_exists:
            self.csv_writer.writerow([
                "document_id",
                "source_url",
                "title",
                "document_type",
                "domain",
                "collection_timestamp",
                "content_hash",
                "publication_date",
            ])
        else:
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    rows = [row for row in reader if row]
                    self.doc_counter = max(0, len(rows) - 1)
            except Exception:
                self.doc_counter = 0

        logger.info("Output JSONL: %s", jsonl_path)
        logger.info("Output CSV:   %s", csv_path)

    def close_spider(self, spider):
        """Close file handles and print crawl summary."""
        if self.jsonl_file:
            self.jsonl_file.close()
        if self.csv_file:
            self.csv_file.close()

        # --- Crawl Summary ---
        stats = spider.crawler_stats
        summary = (
            "\n"
            "=" * 60 + "\n"
            "  CRAWL SUMMARY\n"
            "=" * 60 + "\n"
            f"  Pages visited:          {stats.get('pages_visited', 0)}\n"
            f"  Documents collected:    {stats.get('documents_collected', 0)}\n"
            f"    - HTML documents:     {stats.get('html_collected', 0)}\n"
            f"    - PDF documents:      {stats.get('pdf_collected', 0)}\n"
            f"  Duplicates skipped:     {stats.get('duplicates_skipped', 0)}\n"
            f"  Filtered (irrelevant):  {stats.get('filtered_irrelevant', 0)}\n"
            f"  Errors:                 {stats.get('errors', 0)}\n"
            "=" * 60
        )
        logger.info(summary)

    def process_item(self, item, spider):
        """Assign document_id, write JSONL line, write CSV row."""
        self.doc_counter += 1
        doc_id = f"DOC_{self.doc_counter:06d}"
        item["document_id"] = doc_id

        # --- Write JSONL ---
        record = {
            "document_id": doc_id,
            "source_url": item.get("source_url"),
            "title": item.get("title"),
            "document_type": item.get("document_type"),
            "text": item.get("text"),
            "content_hash": item.get("content_hash"),
            "domain": item.get("domain"),
            "collection_timestamp": item.get("collection_timestamp"),
            "publication_date": item.get("publication_date"),
        }
        self.jsonl_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.jsonl_file.flush()

        # --- Write CSV ---
        self.csv_writer.writerow([
            doc_id,
            item.get("source_url"),
            item.get("title"),
            item.get("document_type"),
            item.get("domain"),
            item.get("collection_timestamp"),
            item.get("content_hash"),
            item.get("publication_date"),
        ])
        self.csv_file.flush()

        # --- Update stats ---
        spider.crawler_stats["documents_collected"] += 1
        doc_type = item.get("document_type", "html")
        if doc_type == "pdf":
            spider.crawler_stats["pdf_collected"] += 1
        else:
            spider.crawler_stats["html_collected"] += 1

        logger.info(
            "SAVED %s [%s] %s — %s",
            doc_id,
            doc_type.upper(),
            item.get("title", "untitled")[:80],
            item.get("source_url"),
        )

        return item
