# Child Protection Information Crawler

> **B.Tech Project Component** — NLP-Based Child Protection Information Extraction Using Named Entity Recognition

## 📋 Project Overview

This is the **web crawler component** of a B.Tech research project focused on extracting child-protection information from publicly accessible documents using Named Entity Recognition (NER).

### What This Crawler Does

- Crawls **publicly accessible** websites from a configurable list of approved sources
- Extracts text from **HTML pages** (removing boilerplate like navigation, scripts, styles)
- Detects and downloads **PDF documents**, extracting their text content
- Saves all collected documents in **JSONL format** with full metadata
- Exports a **metadata CSV** for easy overview of collected documents
- Implements **URL deduplication** and **content deduplication** (SHA-256)
- Provides an optional **keyword relevance filter** for corpus curation
- Respects `robots.txt`, configurable crawl delays, and page limits
- Logs detailed crawl progress and produces a summary report

### What This Crawler Does NOT Do

This crawler is **only** the data collection stage. It does **not** perform:

- ❌ Named Entity Recognition (NER)
- ❌ Text preprocessing, tokenization, stemming, or lemmatization
- ❌ Machine learning or deep learning inference
- ❌ spaCy, BERT, or Hugging Face model usage
- ❌ BIO/IOB2 annotation or automatic labelling
- ❌ Classification, sentiment analysis, or behaviour detection
- ❌ Label Studio integration (the output is designed to be *imported* into Label Studio later)

The collected data will be manually annotated in Label Studio as a separate project stage.

### Ethical & Legal Scope

This crawler is designed for **responsible academic research**:

- Only crawls publicly accessible web pages and documents
- Respects `robots.txt` restrictions by default
- Uses a descriptive User-Agent identifying it as a research crawler
- Implements polite crawl delays and concurrency limits
- Only visits domains explicitly approved in the configuration
- Does **not** bypass access controls, authentication, or encryption
- Does **not** crawl private content, personal data, or restricted material
- Targets only legitimate public sources: government reports, international organization publications, academic research, and public policy documents

---

## 🚀 Installation

### Prerequisites

- **Python 3.11+** installed on your system
- **pip** package manager
- **Git** (optional, for version control)

### Step-by-Step Setup

```bash
# 1. Navigate to the project directory
cd child_protection_crawler

# 2. Create a virtual environment
python -m venv venv

# 3. Activate the virtual environment
#    On Windows:
venv\Scripts\activate
#    On macOS/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
```

### Verify Installation

```bash
# Check Scrapy is installed
scrapy version

# Run the test suite
pytest tests/test_crawler.py -v
```

---

## 📁 Project Structure

```
child_protection_crawler/
│
├── scrapy.cfg                 # Scrapy project configuration
├── requirements.txt           # Python dependencies
├── README.md                  # This file
│
├── crawler/                   # Main Scrapy project package
│   ├── __init__.py
│   ├── items.py               # Data schema (CrawledDocumentItem)
│   ├── pipelines.py           # Processing pipelines (dedup, filter, save)
│   ├── settings.py            # ★ All configuration lives here
│   │
│   └── spiders/               # Spider implementations
│       ├── __init__.py
│       └── public_reports_spider.py  # Main crawl spider
│
├── data/                      # Output directory (created automatically)
│   ├── raw/                   # JSONL output files
│   └── metadata/              # CSV metadata files
│
└── tests/                     # Test suite
    ├── __init__.py
    └── test_crawler.py        # Unit tests (run offline)
```

### File Descriptions

| File | Purpose |
|------|---------|
| `scrapy.cfg` | Tells Scrapy where to find the project settings |
| `requirements.txt` | Lists all Python packages needed |
| `crawler/settings.py` | **Main configuration file** — URLs, domains, limits, keywords |
| `crawler/items.py` | Defines the data fields for each collected document |
| `crawler/pipelines.py` | Processes items: deduplication → relevance filter → save to disk |
| `crawler/spiders/public_reports_spider.py` | The actual spider that crawls pages and extracts text |
| `tests/test_crawler.py` | Automated tests that run without internet access |

---

## ⚙️ Configuration

All configuration is in **`crawler/settings.py`**. Open this file and edit the sections marked with ★.

### 1. Adding Starting URLs

Find the `START_URLS` list and add your approved source URLs:

```python
START_URLS = [
    "https://www.unicef.org/protection",
    "https://www.who.int/health-topics/child-maltreatment",
    "https://www.end-violence.org/reports",
]
```

### 2. Setting Allowed Domains

The crawler will **only** follow links to domains in this list:

```python
ALLOWED_DOMAINS = [
    "www.unicef.org",
    "www.who.int",
    "www.end-violence.org",
]
```

> **Important:** The domain must match exactly. `www.unicef.org` and `unicef.org` are treated as different domains. Include both if needed.

### 3. Changing Crawl Limits

```python
MAX_PAGES = 100              # Maximum documents to collect (0 = unlimited)
DEPTH_LIMIT = 3              # How many link-clicks deep to follow
DOWNLOAD_DELAY = 1.5         # Seconds between requests (be polite!)
CONCURRENT_REQUESTS = 4      # Simultaneous requests
CONCURRENT_REQUESTS_PER_DOMAIN = 2  # Max simultaneous per single domain
```

| Setting | What It Controls | Recommended |
|---------|-----------------|-------------|
| `MAX_PAGES` | Total documents to collect per crawl run | 50–500 |
| `DEPTH_LIMIT` | How far to follow links from start URLs | 2–4 |
| `DOWNLOAD_DELAY` | Politeness delay between requests (seconds) | 1–3 |
| `CONCURRENT_REQUESTS` | Parallel request count | 2–8 |

### 4. Relevance Keywords

Enable/disable the keyword filter and edit the keyword list:

```python
ENABLE_RELEVANCE_FILTER = True  # Set to False to collect everything

RELEVANCE_KEYWORDS = [
    "child protection",
    "child safety",
    "online safety",
    "child exploitation",
    "child safeguarding",
    "online grooming",
    "child abuse",
    "CSEA",
    # Add more keywords here...
]
```

When enabled, only documents containing at least one keyword are saved.

---

## ▶️ Running the Crawler

### Basic Usage

```bash
# Make sure you're in the child_protection_crawler/ directory
# and your virtual environment is activated

scrapy crawl public_reports
```

### With Command-Line Overrides

```bash
# Crawl only 50 pages
scrapy crawl public_reports -a max_pages=50

# Crawl with depth limit of 2
scrapy crawl public_reports -a max_depth=2

# Both overrides together
scrapy crawl public_reports -a max_pages=200 -a max_depth=5
```

### Save Scrapy Log to File

```bash
scrapy crawl public_reports --logfile crawl.log
```

---

## 📄 HTML Text Extraction

The spider extracts meaningful text from HTML pages using BeautifulSoup4 with Python's built-in `html.parser`.

**What is removed:**
- `<script>` and `<style>` elements
- Navigation (`<nav>`), `<header>`, `<footer>` elements
- Forms, iframes, buttons
- Cookie consent banners, social share widgets, sidebars
- All HTML markup tags

**What is kept:**
- Page title
- Headings (h1–h6)
- Paragraphs
- List items
- Table content
- Article/report text
- Blockquotes

The spider first tries to locate the `<main>` or `<article>` element. If not found, it extracts from the full `<body>`. The resulting text is cleaned of excessive whitespace but is otherwise preserved as-is — no NLP preprocessing is applied.

---

## 📑 PDF Handling

The spider detects PDF links (URLs ending in `.pdf` or responses with `Content-Type: application/pdf`).

For each PDF:
1. Downloads the full PDF content
2. Opens it with PyMuPDF (`fitz`)
3. Extracts text from each page
4. Concatenates all page texts
5. Saves the result as a document

**Limitations:**
- Scanned PDFs (images without OCR text layer) will produce empty or minimal text
- Encrypted/password-protected PDFs are skipped gracefully
- Maximum file size: 10 MB (configurable in settings)
- PDF metadata (author, creation date) is not extracted; the URL filename is used as the title

---

## 📊 Output Format

### JSONL Output

Located at: `data/raw/collected_documents.jsonl`

Each line is one JSON document:

```json
{
    "document_id": "DOC_000001",
    "source_url": "https://example.org/child-protection-report-2024.pdf",
    "title": "child protection report 2024",
    "document_type": "pdf",
    "text": "Full extracted text from the document...",
    "content_hash": "a1b2c3d4e5f6...64-character-sha256-hash",
    "domain": "example.org",
    "collection_timestamp": "2026-09-09T06:30:00+00:00",
    "publication_date": null
}
```

```json
{
    "document_id": "DOC_000002",
    "source_url": "https://example.org/online-safety-report",
    "title": "Online Safety Report - Example Organization",
    "document_type": "html",
    "text": "Full extracted text from the web page...",
    "content_hash": "f6e5d4c3b2a1...64-character-sha256-hash",
    "domain": "example.org",
    "collection_timestamp": "2026-09-09T06:31:15+00:00",
    "publication_date": "2024-03-15"
}
```

| Field | Description |
|-------|-------------|
| `document_id` | Sequential ID: DOC_000001, DOC_000002, … |
| `source_url` | URL the document was fetched from |
| `title` | Page title (HTML) or filename (PDF), or `null` |
| `document_type` | `"html"` or `"pdf"` |
| `text` | Full extracted plain text |
| `content_hash` | SHA-256 hash of the text |
| `domain` | Domain name of the source |
| `collection_timestamp` | ISO-8601 timestamp of when it was collected |
| `publication_date` | Publication date if found in meta tags, else `null` |

### Metadata CSV

Located at: `data/metadata/crawl_metadata.csv`

Contains the same fields as the JSONL (minus the full text) for easy overview in Excel or Google Sheets.

---

## 🔁 Deduplication

The crawler implements two levels of deduplication:

### A. URL Deduplication

- The spider normalizes each URL (removes fragments, trailing slashes, lowercases host).
- A set of visited URLs is maintained in memory.
- If a URL has already been visited, it is skipped.
- This prevents the same page from being requested twice.

### B. Content Deduplication

- After extracting text, a **SHA-256 hash** is computed from the full text.
- The `DeduplicationPipeline` maintains a set of all seen hashes.
- If a new document's hash matches a previously seen hash, it is dropped.
- This catches cases where different URLs serve identical content (mirrors, redirects, etc.).

---

## 📈 Logging

The crawler logs detailed information during the crawl:

```
2026-09-09 12:00:01 [public_reports] INFO: Starting crawl with 3 URL(s).
2026-09-09 12:00:01 [public_reports] INFO: Allowed domains: ['example.org']
2026-09-09 12:00:02 [public_reports] INFO: VISITING [1]: https://example.org/reports
2026-09-09 12:00:03 [crawler.pipelines] INFO: SAVED DOC_000001 [HTML] Example Report — https://example.org/reports
2026-09-09 12:00:05 [public_reports] INFO: PDF DISCOVERED: https://example.org/report.pdf
2026-09-09 12:00:07 [crawler.pipelines] INFO: SAVED DOC_000002 [PDF] report — https://example.org/report.pdf
2026-09-09 12:00:08 [crawler.pipelines] INFO: DUPLICATE CONTENT skipped (hash=a1b2c3d4...): https://example.org/duplicate
```

### Crawl Summary

At the end of each crawl, a summary is printed:

```
============================================================
  CRAWL SUMMARY
============================================================
  Pages visited:          87
  Documents collected:    62
    - HTML documents:     45
    - PDF documents:      17
  Duplicates skipped:     12
  Filtered (irrelevant):  13
  Errors:                 3
============================================================
```

---

## 🧪 Testing

Run the full test suite:

```bash
pytest tests/test_crawler.py -v
```

Tests cover:
- URL normalization and deduplication
- Content hash deduplication
- HTML text extraction (removes scripts, styles, nav; keeps content)
- PDF text extraction (creates synthetic PDFs for testing)
- Metadata record structure and JSON serialization
- Relevance keyword filter (pass/reject/disabled)
- Allowed domain filtering

All tests run **offline** — no internet connection required.

---

## 🔗 Importing into Label Studio (Next Stage)

The JSONL output is designed to be easily imported into Label Studio for manual NER annotation.

### Steps (for the next project stage):

1. **Install Label Studio:**
   ```bash
   pip install label-studio
   label-studio start
   ```

2. **Create a new project** in the Label Studio web interface.

3. **Import the JSONL file:**
   - Go to your project → **Import**
   - Upload `data/raw/collected_documents.jsonl`
   - Label Studio will create one task per JSON line

4. **Configure the labelling template** for NER:
   ```xml
   <View>
     <Header value="Source: $source_url" />
     <Text name="text" value="$text" />
     <Labels name="label" toName="text">
       <Label value="PERSON" />
       <Label value="ORGANIZATION" />
       <Label value="LOCATION" />
       <Label value="DATE" />
       <!-- Add your custom entity labels here -->
     </Labels>
   </View>
   ```

5. **Annotate** documents by highlighting text spans and assigning entity labels.

6. **Export** annotations in your preferred format (e.g., CoNLL, JSON) for NER model training.

> This import workflow is for the **next stage** of the project. The crawler itself does not interact with Label Studio.

---

## ⚠️ Limitations

- **Scanned PDFs:** PDFs that are scanned images (no text layer) will yield empty text. OCR is not implemented.
- **JavaScript-rendered pages:** Pages that require JavaScript execution to load content will not be fully extracted. The crawler fetches raw HTML only.
- **Large crawls:** For very large crawls (thousands of pages), consider increasing `DOWNLOAD_DELAY` and monitoring memory usage.
- **Rate limiting:** Some websites may temporarily block the crawler despite polite delays. Increase `DOWNLOAD_DELAY` if you encounter HTTP 429 errors.
- **Subdomain matching:** `example.org` and `www.example.org` are treated as different domains. Include both in `ALLOWED_DOMAINS` if needed.

---

## 📝 Quick Reference

| Task | How |
|------|-----|
| Add a source URL | Edit `START_URLS` in `crawler/settings.py` |
| Add an allowed domain | Edit `ALLOWED_DOMAINS` in `crawler/settings.py` |
| Change page limit | Edit `MAX_PAGES` in `crawler/settings.py` |
| Change crawl depth | Edit `DEPTH_LIMIT` in `crawler/settings.py` |
| Change delay | Edit `DOWNLOAD_DELAY` in `crawler/settings.py` |
| Change concurrency | Edit `CONCURRENT_REQUESTS` in `crawler/settings.py` |
| Edit keywords | Edit `RELEVANCE_KEYWORDS` in `crawler/settings.py` |
| Disable keyword filter | Set `ENABLE_RELEVANCE_FILTER = False` |
| Run the crawler | `scrapy crawl public_reports` |
| Run with page limit | `scrapy crawl public_reports -a max_pages=50` |
| Run tests | `pytest tests/test_crawler.py -v` |
| View output | Open `data/raw/collected_documents.jsonl` |
| View metadata | Open `data/metadata/crawl_metadata.csv` |

---

## 📜 License

This project is developed for academic/research purposes as part of a B.Tech final-year project.
