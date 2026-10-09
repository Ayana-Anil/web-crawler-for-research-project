# Child Protection Crawler - Scrapy Settings
# =============================================================================
#
# This file contains ALL the configuration you need to modify.
# Scroll down to the sections marked with ★ to configure your crawl.
#
# =============================================================================


# ★ SECTION 1: STARTING URLS
# ---------------------------------------------------------------------------
# Add the publicly accessible URLs you want the crawler to start from.
# These should be pages that link to child-protection reports, publications,
# or documents from trusted public sources.
#
# HOW TO EDIT:
#   - Add a new URL string inside the list below.
#   - Make sure each URL is enclosed in quotes and separated by commas.
#   - Remove any URL you no longer want to crawl.
#
# Example:
#   START_URLS = [
#       "https://www.unicef.org/protection",
#       "https://www.who.int/health-topics/child-maltreatment",
#   ]
# ---------------------------------------------------------------------------

START_URLS = [
    "https://www.internetmatters.org/",
]


# ★ SECTION 2: ALLOWED DOMAINS
# ---------------------------------------------------------------------------
# The crawler will ONLY follow links that belong to these domains.
# This prevents the crawler from wandering off to unrelated websites.
#
# HOW TO EDIT:
#   - Add the domain (without https:// or trailing slash).
#   - Each domain is a string in the list.
#
# Example:
#   ALLOWED_DOMAINS = [
#       "www.unicef.org",
#       "www.who.int",
#   ]
# ---------------------------------------------------------------------------

ALLOWED_DOMAINS = [
    "www.internetmatters.org",
]


# ★ SECTION 3: RELEVANCE KEYWORDS (Optional)
# ---------------------------------------------------------------------------
# If ENABLE_RELEVANCE_FILTER is True, the crawler will only save documents
# whose text contains at least one of these keywords (case-insensitive).
#
# Set ENABLE_RELEVANCE_FILTER = False to collect ALL documents from the
# allowed domains without any keyword filtering.
#
# HOW TO EDIT:
#   - Add or remove keyword strings in the list below.
#   - Keywords are matched case-insensitively against the full document text.
#   - A document is considered relevant if ANY keyword appears in its text.
# ---------------------------------------------------------------------------

ENABLE_RELEVANCE_FILTER = False

RELEVANCE_KEYWORDS = [
    "child protection",
    "child safety",
    "online safety",
    "child exploitation",
    "child safeguarding",
    "online grooming",
    "child abuse",
    "CSEA",
    "child maltreatment",
    "child welfare",
    "child trafficking",
    "child labour",
    "child labor",
    "violence against children",
    "online child safety",
]


# ★ SECTION 4: CRAWL LIMITS
# ---------------------------------------------------------------------------
# These settings control how much the crawler collects.
#
# MAX_PAGES:
#   Maximum number of pages/documents to collect in one crawl run.
#   Set to 0 for unlimited (not recommended for first runs).
#
# MAX_DEPTH (DEPTH_LIMIT):
#   How many "clicks" deep the crawler will follow links from the start URL.
#   Depth 0 = only the start URLs themselves.
#   Depth 1 = start URLs + pages linked from them.
#   Depth 3 = a reasonable default for most research crawls.
#
# DOWNLOAD_DELAY:
#   Seconds to wait between consecutive requests to the same domain.
#   Higher = more polite but slower.  1-2 seconds is standard.
#
# CONCURRENT_REQUESTS:
#   Number of simultaneous requests.
#   Lower values are more polite to the server.
# ---------------------------------------------------------------------------

MAX_PAGES = 50
DEPTH_LIMIT = 3
DOWNLOAD_DELAY = 1.0
CONCURRENT_REQUESTS = 2
CONCURRENT_REQUESTS_PER_DOMAIN = 1


# ★ SECTION 5: OUTPUT PATHS
# ---------------------------------------------------------------------------
# Where collected data will be saved.
# By default these are relative to the child_protection_crawler/ directory.
# You can use absolute paths if you prefer.
# ---------------------------------------------------------------------------

import os

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(_PROJECT_DIR, "data")
RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")
METADATA_DIR = os.path.join(DATA_DIR, "metadata")

# Output filenames
JSONL_FILENAME = "collected_documents.jsonl"
METADATA_CSV_FILENAME = "crawl_metadata.csv"


# =============================================================================
# ADVANCED SETTINGS (you probably don't need to change these)
# =============================================================================

BOT_NAME = "child_protection_crawler"

SPIDER_MODULES = ["crawler.spiders"]
NEWSPIDER_MODULE = "crawler.spiders"

# --- Crawler Identity ---
# A descriptive User-Agent so website administrators can identify this crawler.
USER_AGENT = (
    "ChildProtectionResearchCrawler/1.0 "
    "(+BTech Research Project; NLP-based child protection information extraction; "
    "respectful academic crawler)"
)

# --- Robots.txt ---
# Respect robots.txt by default. Do NOT change this to False.
ROBOTSTXT_OBEY = True

# --- Request Settings ---
# Timeout for individual requests (seconds).
DOWNLOAD_TIMEOUT = 30

# Maximum response size (bytes). 10 MB limit for PDFs.
DOWNLOAD_MAXSIZE = 10 * 1024 * 1024  # 10 MB

# Retry failed requests up to 2 times.
RETRY_TIMES = 2
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# --- Pipeline ---
# The pipeline processes and saves each collected item.
ITEM_PIPELINES = {
    "crawler.pipelines.DeduplicationPipeline": 100,
    "crawler.pipelines.RelevanceFilterPipeline": 200,
    "crawler.pipelines.DataStoragePipeline": 300,
}

# --- Logging ---
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
LOG_DATEFORMAT = "%Y-%m-%d %H:%M:%S"

# --- AutoThrottle (optional, adjusts delay automatically) ---
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

# --- HTTP Cache (useful during development to avoid re-downloading) ---
# Set to True during development/testing, False for production crawls.
HTTPCACHE_ENABLED = False
HTTPCACHE_EXPIRATION_SECS = 86400  # 24 hours
HTTPCACHE_DIR = "httpcache"

# --- Feeds ---
# We handle output manually in pipelines for full control.
# Do not add FEEDS configuration here.

# Obey depth limit
DEPTH_PRIORITY = 1
SCHEDULER_DISK_QUEUE = "scrapy.squeues.PickleFifoDiskQueue"
SCHEDULER_MEMORY_QUEUE = "scrapy.squeues.FifoMemoryQueue"

# --- Request fingerprinting ---
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"

# --- Twisted reactor ---
# NOTE: Scrapy 2.18 defaults to AsyncioSelectorReactor, which can silently
# fail on Windows. We explicitly use the select-based reactor instead.
TWISTED_REACTOR = "twisted.internet.selectreactor.SelectReactor"
