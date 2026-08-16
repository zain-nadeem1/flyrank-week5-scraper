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
