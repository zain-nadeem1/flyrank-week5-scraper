# FlyRank Internship A9 — The Polite Scraper

A Python web scraper built for the **FlyRank Backend Track — Week 5 — Assignment A9**.

The project collects books from the first three catalogue pages of **Books to Scrape**, extracts their details, cleans and validates the data, stores it as JSON, handles broken pages safely, and produces a report for every run.

## Target Classification

### Target

**Books to Scrape**
https://books.toscrape.com/

Books to Scrape is a public practice sandbox specifically designed for learning and testing web scraping.

For this assignment, the scraper is limited to:

* The first 3 catalogue pages
* 60 discovered book pages
* Only the data required by the assignment

I checked:

https://books.toscrape.com/robots.txt

The request returned **HTTP 404**, meaning no robots.txt file was found. A missing robots.txt file was not treated as permission by itself.

I will not reuse this code on another site without checking its rules and terms first.

## Technology

**Language:** Python 3.10+

**Libraries:**

* Requests — HTTP requests
* Beautiful Soup — HTML parsing
* Pydantic — schema validation

## Installation

Create and activate a virtual environment:

```bash
python -m venv venv
```

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

Run the scraper with:

```bash
python src/main.py
```

The scraper processes the first three catalogue pages and discovers 60 unique book URLs.

The results are written to:

```text
output/books.json
output/errors.json
output/run-report.json
```

## Scraping Pipeline

```text
Fetch
  ↓
Cache
  ↓
Discover 3 catalogue pages
  ↓
Discover 60 unique book URLs
  ↓
Fetch book pages
  ↓
Extract raw data
  ↓
Normalize values
  ↓
Validate with Pydantic
  ↓
Store valid records
  ↓
Generate run report
```

## Record Schema

Each valid book contains:

```json
{
  "title": "A Light in the Attic",
  "product_url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
  "price_text": "£51.77",
  "price_gbp": 51.77,
  "availability_text": "In stock (22 available)",
  "rating_text": "Three",
  "description": "...",
  "source_page": "https://books.toscrape.com/catalogue/page-1.html",
  "fetched_at": "2026-08-16T..."
}
```

### Fields

| Field               | Type        | Purpose                           |
| ------------------- | ----------- | --------------------------------- |
| `title`             | string      | Book title                        |
| `product_url`       | URL         | Absolute book URL                 |
| `price_text`        | string      | Original price                    |
| `price_gbp`         | number      | Clean numeric price               |
| `availability_text` | string      | Stock information                 |
| `rating_text`       | string      | Book rating                       |
| `description`       | string/null | Book description                  |
| `source_page`       | URL         | Catalogue page where it was found |
| `fetched_at`        | string      | UTC fetch timestamp               |

## Validation and Storage

Every record is validated with **Pydantic** before being stored.

Valid records are written to:

```text
output/books.json
```

Invalid records are written to:

```text
output/errors.json
```

A failed validation never enters `books.json`.

The product URL is used as the record identity, and duplicate URLs are removed before processing.

A clean run produces **60 unique validated records**.

Running the scraper again does not append duplicate records, making the output idempotent.

## Politeness Rules

The scraper follows these rules:

* Uses an identifying User-Agent.
* Uses a **10-second request timeout**.
* Waits at least **0.5 seconds** between real requests.
* Checks HTTP status codes before parsing.
* Retries timeouts and server errors once.
* Does not retry HTTP 403 or 404.
* Saves downloaded pages in a local cache.
* Uses cached pages during development instead of repeatedly requesting the website.

The cache is excluded from Git.

## Failure Handling

Each book page is processed independently.

If one page fails, the scraper records the failure and continues processing the remaining books instead of crashing.

For the Stage 5 failure test, a deliberately fake URL was added. The scraper completed successfully and preserved the 60 valid records while reporting:

```text
valid_records=60
failed_pages=1
```

The normal clean run has:

```text
valid_records=60
invalid_records=0
failed_pages=0
```

## Run Report

Every run creates:

```text
output/run-report.json
```

It records:

* Start time
* Duration
* Catalogue pages
* Detail pages
* Pages fetched
* Cache hits
* Valid records
* Invalid records
* Failed pages
* Failed URLs

Example clean run:

```json
{
  "catalogue_pages": 3,
  "detail_pages": 60,
  "valid_records": 60,
  "invalid_records": 0,
  "failed_pages": 0
}
```

The complete report is available in `output/run-report.json`.

## Why No Browser?

A browser is not required because the book information needed for this assignment is already present in the HTML returned by the server. Using a browser would add unnecessary startup time and memory usage.

## Ethics

This project targets a scraping practice sandbox and collects only the information required for the assignment.

For real websites:

* Use an official API when one exists.
* Check the site's rules and terms first.
* Respect robots.txt where applicable.
* Never bypass logins, paywalls, CAPTCHAs, or blocks.
* Identify the scraper honestly.
* Avoid unnecessary requests.
* Collect only the data that is needed.

## Limitation

The scraper depends on the current HTML structure and CSS selectors of Books to Scrape. If the site's structure changes, the selectors may need to be updated.

The scraper is intentionally limited to the first three catalogue pages rather than crawling the entire website.

## Project Structure

```text
scraper/
├── src/
│   └── main.py
├── output/
│   ├── books.json
│   ├── errors.json
│   └── run-report.json
├── cache/
├── .gitignore
├── README.md
└── requirements.txt
```

The `cache/` directory is intentionally excluded from Git.

## Stage 6 Checkpoint

The final clean run successfully produced:

```text
catalogue_pages=3
discovered=60
unique_urls=60
valid_records=60
invalid_records=0
failed_pages=0
```

The failure test also confirmed that one broken page does not stop the scraper:

```text
valid_records=60
failed_pages=1
```

The project is ready to be run by another developer using the documented installation and run command.

---

## AI vs Me

For the AI rematch, I asked another AI to build the same scraper independently. I kept the original hand-built version untouched and reviewed the generated implementation against my Stage 4/5 requirements and checkpoints.

### Prompt used

> Build a Python web scraper for Books to Scrape. Scrape exactly the first 3 catalogue pages and discover the 60 unique book detail URLs from those pages.
>
> For every book detail page, collect these 8 raw fields:
> title, product_url, price_text, availability_text, rating_text, description, source_page, fetched_at.
>
> Normalize the price into a numeric `price_gbp` field and validate every final record with Pydantic before storing it.
>
> The scraper must use requests and BeautifulSoup, not a browser. Every real HTTP request must use an identifying User-Agent, a timeout, an HTTP status-code check, and at least a 500 ms delay between requests. Use a local cache so development reruns can read cached HTML without making unnecessary network requests.
>
> De-duplicate books by product URL. A broken detail-page URL must not crash the whole run: log the failure and continue processing the remaining books.
>
> Produce books.json, errors.json, and run-report.json. The run report should include discovered URLs, unique URLs, detail pages, fetched pages, cache hits, valid records, invalid records, failed pages, and duration.
>
> The expected successful result is 60 unique book URLs and 60 valid records. A rerun should not create duplicate records.
>
> Keep the implementation reasonably simple and readable. Explain any important design decisions.

### What the AI did better

1. **Price normalization was more robust.**  
   The AI noticed that the scraped price could contain encoding artifacts such as `Â£51.77` and used a regular expression to extract the numeric portion instead of directly calling `float()` on the raw string.

2. **Retry handling was improved.**  
   The AI version added a single retry for request timeouts and HTTP 5xx errors while avoiding retries for 403 and 404 responses.

3. **The code was well separated into functions.**  
   Fetching, caching, catalogue discovery, extraction, normalization, validation, and output writing were separated into clear sections, making the implementation easier to inspect.

### What the AI got wrong or silently skipped

1. **The test/broken-URL checkpoint was not preserved.**  
   My Stage 5 implementation specifically tested failure handling with a deliberately broken URL. The AI version only handles failures if they occur naturally; it does not include a clear configurable test URL/checkpoint for deliberately proving that a broken page is logged and skipped.

2. **The run report is less detailed about failures.**  
   It reports the number of failed pages, but does not preserve as much structured failure information in `run-report.json`; the detailed failures are instead stored in `errors.json`.

3. **The AI did not fully reproduce my checkpoint workflow.**  
   The assignment is not only about producing working scraper code. It also requires proving specific behaviours, especially the broken-page test and rerun/cache behaviour. The AI implementation focuses more on the scraper itself than on reproducing the complete evidence/checkpoint process.

### What my prompt forgot to say

My prompt did not explicitly specify the exact structure of the Stage 5 checkpoint and evidence requirements.

In particular, I should have explicitly told the AI to:

- include a deliberately broken test URL;
- report the result of that broken-URL test;
- preserve the exact expected `errors.json` structure;
- reproduce the same validation and rerun checkpoints as my hand-built implementation;
- distinguish between a naturally failed page and the deliberately injected test failure.

Because these details were not explicit enough in my prompt, the AI reasonably concentrated on building the scraper rather than reproducing every part of my testing workflow.

### Checkpoint comparison

| Checkpoint | My version | AI version |
|---|---|---|
| First 3 catalogue pages | Passed | Implemented |
| 60 unique books | Passed | Designed for 60 |
| Eight raw fields | Passed | Passed |
| Numeric `price_gbp` | Passed after encoding fix | Better handling of encoding artifacts |
| Pydantic validation | Passed | Passed |
| Duplicate prevention | Passed | Passed |
| Cache support | Passed | Passed |
| User-Agent | Passed | Passed |
| 500 ms request delay | Passed | Passed |
| Timeout | Passed | Passed |
| HTTP status checking | Passed | Passed |
| Broken-page handling | Passed | Handles failures, but no explicit checkpoint |
| Run report | Passed | Passed |
| Rerun without duplicates | Passed | Designed to pass |
| Exact Stage 5 evidence workflow | Passed | Partially reproduced |

### Three concrete differences

**1. Price handling**

My original implementation initially exposed an encoding problem with prices such as `Â£51.77`. The AI version handled this more defensively by removing non-numeric characters before converting the price to `float`.

**2. Retry behaviour**

My implementation focused on the assignment's required failure handling, while the AI added a retry mechanism for timeouts and server-side 5xx errors. This is useful, but it also introduces behaviour that was not necessary for the core checkpoint.

**3. Testing vs implementation**

My version was built around the assignment checkpoints, including deliberately testing a broken URL. The AI version mainly implements the scraper pipeline and failure handling but does not explicitly reproduce that deliberate failure test.

### Final assessment

The AI produced a clean and reasonably strong scraper, and in a few areas—especially price normalization and retry handling—it was better than my first implementation. However, it did not completely reproduce the engineering evidence and checkpoint workflow I had already built.

The main lesson was that **the quality of an AI-generated implementation depends heavily on the specification given to it**. My prompt described the scraper well, but I did not describe every testing and evidence requirement precisely enough. Building the original version first made it much easier to identify these omissions.