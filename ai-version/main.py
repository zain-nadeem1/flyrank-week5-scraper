"""
main.py — Practice web scraper for https://books.toscrape.com/

Scrapes the first 3 catalogue pages, discovers all book detail-page links from
them, visits every detail page, extracts + normalizes + validates the book
data, and writes:

    output/books.json
    output/errors.json
    output/run-report.json

See the bottom of this file / the README explanation for how to run it.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, HttpUrl, ValidationError

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

CATALOGUE_START_URL = "https://books.toscrape.com/catalogue/page-1.html"
MAX_CATALOGUE_PAGES = 3

CACHE_DIR = Path("cache")
OUTPUT_DIR = Path("output")

USER_AGENT = "FlyRankInternshipA9/1.0 (+https://github.com/YOUR_USERNAME/YOUR_REPO)"
REQUEST_TIMEOUT = 10  # seconds
MIN_DELAY_BETWEEN_REQUESTS = 0.5  # seconds, real network requests only
RETRY_DELAY = 1.0  # seconds, before a single retry on timeout / 5xx


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

class FetchError(Exception):
    """Raised when a URL could not be fetched successfully (no more retries left)."""

    def __init__(self, url: str, reason: str):
        self.url = url
        self.reason = reason
        super().__init__(f"{url} -> {reason}")


class Stats:
    """Tiny mutable bag of counters shared across the run."""

    def __init__(self):
        self.pages_fetched = 0
        self.cache_hits = 0


def slugify_for_cache(url: str) -> str:
    """Turn a URL into a filesystem-safe slug for cache filenames."""
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if not parts:
        slug = "root"
    elif parts[-1] == "index.html" and len(parts) >= 2:
        slug = parts[-2]
    else:
        slug = parts[-1]
    slug = re.sub(r"[^A-Za-z0-9_\-]", "_", slug)
    return slug or "page"


# --------------------------------------------------------------------------
# Fetching + caching
# --------------------------------------------------------------------------

def _download(url: str) -> str:
    """
    Perform the actual HTTP GET with politeness rules:
      - identifying User-Agent
      - timeout
      - 200 is the only success
      - 403 / 404 are never retried
      - timeouts / 5xx get exactly one retry after a short delay
      - always pause after a real request
    """
    headers = {"User-Agent": USER_AGENT}

    for attempt in (1, 2):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout:
            if attempt == 1:
                time.sleep(RETRY_DELAY)
                continue
            raise FetchError(url, "request timed out (after retry)")
        except requests.exceptions.RequestException as exc:
            time.sleep(MIN_DELAY_BETWEEN_REQUESTS)
            raise FetchError(url, f"request error: {exc}")

        # Politeness pause after every real request that reached the server.
        time.sleep(MIN_DELAY_BETWEEN_REQUESTS)

        if response.status_code == 200:
            # The site declares utf-8; force it to avoid mojibake around "£".
            response.encoding = "utf-8"
            return response.text

        if response.status_code in (403, 404):
            raise FetchError(url, f"HTTP {response.status_code}")

        if 500 <= response.status_code < 600:
            if attempt == 1:
                time.sleep(RETRY_DELAY)
                continue
            raise FetchError(url, f"HTTP {response.status_code} (after retry)")

        # Any other status code: treat as a hard failure, no retry.
        raise FetchError(url, f"HTTP {response.status_code}")

    raise FetchError(url, "failed after retries")


def fetch_url(url: str, cache_path: Path, stats: Stats) -> str:
    """
    Fetch a URL, transparently using the local cache when available.
    Updates `stats` and prints a CACHE HIT / FETCH line. Never prints HTML.
    """
    if cache_path.exists():
        html = cache_path.read_text(encoding="utf-8")
        stats.cache_hits += 1
        print(f"CACHE HIT | {url} | size={len(html.encode('utf-8'))} bytes")
        return html

    html = _download(url)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(html, encoding="utf-8")
    stats.pages_fetched += 1
    print(f"FETCH | {url} | size={len(html.encode('utf-8'))} bytes")
    return html


# --------------------------------------------------------------------------
# Catalogue discovery
# --------------------------------------------------------------------------

def discover_catalogue_and_books(stats: Stats):
    """
    Walk the catalogue pages (following the site's own "next" link), stopping
    after MAX_CATALOGUE_PAGES. Returns:
      - catalogue_pages: list of catalogue page URLs actually visited
      - book_links: list of (absolute_book_url, source_catalogue_page_url) tuples,
        in discovery order, possibly containing duplicates.
    """
    catalogue_pages: list[str] = []
    book_links: list[tuple[str, str]] = []

    current_url = CATALOGUE_START_URL

    for page_num in range(1, MAX_CATALOGUE_PAGES + 1):
        cache_path = CACHE_DIR / f"catalogue-page-{page_num}.html"
        html = fetch_url(current_url, cache_path, stats)
        soup = BeautifulSoup(html, "html.parser")
        catalogue_pages.append(current_url)

        for anchor in soup.select("article.product_pod h3 a"):
            href = anchor.get("href")
            if not href:
                continue
            absolute_url = urljoin(current_url, href)
            book_links.append((absolute_url, current_url))

        if page_num == MAX_CATALOGUE_PAGES:
            break

        next_anchor = soup.select_one("li.next a")
        if not next_anchor or not next_anchor.get("href"):
            break  # site ran out of pages before we hit our own limit

        current_url = urljoin(current_url, next_anchor["href"])

    return catalogue_pages, book_links


# --------------------------------------------------------------------------
# Book detail extraction
# --------------------------------------------------------------------------

def extract_book(html: str, product_url: str, source_page: str, fetched_at: str) -> dict:
    """Pull the raw fields out of a book detail page. Missing description -> None."""
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.select_one("div.product_main h1")
    title = title_tag.get_text(strip=True) if title_tag else None

    price_tag = soup.select_one("p.price_color")
    price_text = price_tag.get_text(strip=True) if price_tag else None

    availability_tag = soup.select_one("p.availability")
    availability_text = availability_tag.get_text(strip=True) if availability_tag else None

    rating_tag = soup.select_one("p.star-rating")
    rating_text = None
    if rating_tag:
        for css_class in rating_tag.get("class", []):
            if css_class != "star-rating":
                rating_text = css_class
                break

    description = None
    description_heading = soup.select_one("#product_description")
    if description_heading:
        description_paragraph = description_heading.find_next_sibling("p")
        if description_paragraph:
            description = description_paragraph.get_text(strip=True)

    return {
        "title": title,
        "product_url": product_url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": fetched_at,
    }


# --------------------------------------------------------------------------
# Normalization
# --------------------------------------------------------------------------

def normalize_price(price_text: Optional[str]) -> float:
    """
    Convert a price string like "£51.77" (or one containing encoding
    artifacts such as "Â£51.77") into 51.77, without relying on float()
    directly on the raw text.
    """
    if not price_text:
        raise ValueError("price_text is missing")

    cleaned = re.sub(r"[^0-9.]", "", price_text)
    if not cleaned or cleaned.count(".") > 1:
        raise ValueError(f"could not extract a numeric price from {price_text!r}")

    return float(cleaned)


# --------------------------------------------------------------------------
# Validation schema
# --------------------------------------------------------------------------

class BookRecord(BaseModel):
    title: str
    product_url: HttpUrl
    price_text: str
    price_gbp: float
    availability_text: str
    rating_text: str
    description: Optional[str] = None
    source_page: HttpUrl
    fetched_at: str


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------
# Main pipeline
# --------------------------------------------------------------------------

def main() -> None:
    stats = Stats()
    run_started_at = datetime.now(timezone.utc)
    run_start_perf = time.perf_counter()

    catalogue_pages, book_link_pairs = discover_catalogue_and_books(stats)
    discovered = len(book_link_pairs)

    # De-duplicate using the absolute product_url as identity, keeping the
    # first catalogue page a URL was seen on.
    unique_books: dict[str, str] = {}
    for url, source_page in book_link_pairs:
        if url not in unique_books:
            unique_books[url] = source_page
    unique_urls = len(unique_books)

    valid_records: list[BookRecord] = []
    invalid_records: list[dict] = []
    failed_pages: list[dict] = []

    for product_url, source_page in unique_books.items():
        cache_path = CACHE_DIR / f"detail-{slugify_for_cache(product_url)}.html"

        try:
            html = fetch_url(product_url, cache_path, stats)
        except FetchError as exc:
            failed_pages.append({"url": product_url, "reason": exc.reason})
            continue

        fetched_at = datetime.now(timezone.utc).isoformat()
        raw = None
        try:
            raw = extract_book(html, product_url, source_page, fetched_at)
            price_gbp = normalize_price(raw["price_text"])
            record = BookRecord(**raw, price_gbp=price_gbp)
            valid_records.append(record)
        except (ValidationError, ValueError, TypeError) as exc:
            error_entry = dict(raw) if raw else {"product_url": product_url}
            error_entry["error_reason"] = str(exc)
            invalid_records.append(error_entry)

    # --- write outputs ---------------------------------------------------
    books_json = [json.loads(record.model_dump_json()) for record in valid_records]
    save_json(OUTPUT_DIR / "books.json", books_json)

    errors_json = {
        "invalid_records": invalid_records,
        "failed_pages": failed_pages,
    }
    save_json(OUTPUT_DIR / "errors.json", errors_json)

    duration_seconds = round(time.perf_counter() - run_start_perf, 3)
    run_report = {
        "start_time": run_started_at.isoformat(),
        "duration_seconds": duration_seconds,
        "catalogue_pages": len(catalogue_pages),
        "discovered": discovered,
        "unique_urls": unique_urls,
        "detail_pages": unique_urls,
        "pages_fetched": stats.pages_fetched,
        "cache_hits": stats.cache_hits,
        "valid_records": len(valid_records),
        "invalid_records": len(invalid_records),
        "failed_pages": len(failed_pages),
    }
    save_json(OUTPUT_DIR / "run-report.json", run_report)

    print("\n--- run report ---")
    print(json.dumps(run_report, indent=2))


if __name__ == "__main__":
    main()
