from __future__ import annotations

import csv
import hashlib
import html
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


CATALOGUE_START_URL = (
    "https://books.toscrape.com/catalogue/page-1.html"
)

MAX_CATALOGUE_PAGES = 3

CACHE_DIR = Path("cache")
OUTPUT_DIR = Path("output")

USER_AGENT = (
    "FlyRankInternshipA9/1.0 "
    "(+https://github.com/YOUR_USERNAME/YOUR_REPO)"
)

REQUEST_TIMEOUT = 10
MIN_DELAY_BETWEEN_REQUESTS = 0.5
RETRY_DELAY = 1.0


class FetchError(Exception):
    def __init__(self, url: str, reason: str):
        self.url = url
        self.reason = reason
        super().__init__(f"{url} -> {reason}")


class Stats:
    def __init__(self):
        self.pages_fetched = 0
        self.cache_hits = 0


def slugify_for_cache(url: str) -> str:
    parsed = urlparse(url)

    parts = [p for p in parsed.path.split("/") if p]

    if not parts:
        slug = "root"

    elif parts[-1] == "index.html" and len(parts) >= 2:
        slug = parts[-2]

    else:
        slug = parts[-1]

    slug = re.sub(r"[^A-Za-z0-9_-]", "_", slug)

    return slug or "page"


def _download(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT
    }

    for attempt in (1, 2):

        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )

        except requests.exceptions.Timeout:

            if attempt == 1:
                time.sleep(RETRY_DELAY)
                continue

            raise FetchError(
                url,
                "request timed out (after retry)"
            )

        except requests.exceptions.RequestException as exc:

            time.sleep(MIN_DELAY_BETWEEN_REQUESTS)

            raise FetchError(
                url,
                f"request error: {exc}"
            )

        time.sleep(MIN_DELAY_BETWEEN_REQUESTS)

        if response.status_code == 200:
            response.encoding = "utf-8"

            return response.text

        if response.status_code in (403, 404):

            raise FetchError(
                url,
                f"HTTP {response.status_code}"
            )

        if 500 <= response.status_code < 600:

            if attempt == 1:
                time.sleep(RETRY_DELAY)
                continue

            raise FetchError(
                url,
                f"HTTP {response.status_code} (after retry)"
            )

        raise FetchError(
            url,
            f"HTTP {response.status_code}"
        )

    raise FetchError(
        url,
        "failed after retries"
    )


def fetch_url(
    url: str,
    cache_path: Path,
    stats: Stats,
) -> str:
    if cache_path.exists():

        html_text = cache_path.read_text(
            encoding="utf-8"
        )

        stats.cache_hits += 1

        print(
            f"CACHE HIT | {url} | "
            f"size={len(html_text.encode('utf-8'))} bytes"
        )

        return html_text

    html_text = _download(url)

    cache_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    cache_path.write_text(
        html_text,
        encoding="utf-8"
    )

    stats.pages_fetched += 1

    print(
        f"FETCH | {url} | "
        f"size={len(html_text.encode('utf-8'))} bytes"
    )

    return html_text


def discover_catalogue_and_books(stats: Stats):
    catalogue_pages: list[str] = []

    book_links: list[tuple[str, str]] = []

    current_url = CATALOGUE_START_URL

    for page_num in range(
        1,
        MAX_CATALOGUE_PAGES + 1
    ):

        cache_path = (
            CACHE_DIR
            / f"catalogue-page-{page_num}.html"
        )

        html_text = fetch_url(
            current_url,
            cache_path,
            stats
        )

        soup = BeautifulSoup(
            html_text,
            "html.parser"
        )

        catalogue_pages.append(
            current_url
        )

        for anchor in soup.select(
            "article.product_pod h3 a"
        ):

            href = anchor.get("href")

            if not href:
                continue

            absolute_url = urljoin(
                current_url,
                href
            )

            book_links.append(
                (
                    absolute_url,
                    current_url
                )
            )

        if page_num == MAX_CATALOGUE_PAGES:
            break

        next_anchor = soup.select_one(
            "li.next a"
        )

        if (
            not next_anchor
            or not next_anchor.get("href")
        ):
            break

        current_url = urljoin(
            current_url,
            next_anchor["href"]
        )

    return catalogue_pages, book_links


def extract_book(
    html_text: str,
    product_url: str,
    source_page: str,
    fetched_at: str,
) -> dict:
    soup = BeautifulSoup(
        html_text,
        "html.parser"
    )

    title_tag = soup.select_one(
        "div.product_main h1"
    )

    title = (
        title_tag.get_text(strip=True)
        if title_tag
        else None
    )

    price_tag = soup.select_one(
        "p.price_color"
    )

    price_text = (
        price_tag.get_text(strip=True)
        if price_tag
        else None
    )

    availability_tag = soup.select_one(
        "p.availability"
    )

    availability_text = (
        availability_tag.get_text(strip=True)
        if availability_tag
        else None
    )

    rating_tag = soup.select_one(
        "p.star-rating"
    )

    rating_text = None

    if rating_tag:

        for css_class in rating_tag.get(
            "class",
            []
        ):

            if css_class != "star-rating":

                rating_text = css_class

                break

    description = None

    description_heading = soup.select_one(
        "#product_description"
    )

    if description_heading:

        description_paragraph = (
            description_heading
            .find_next_sibling("p")
        )

        if description_paragraph:

            description = (
                description_paragraph
                .get_text(strip=True)
            )

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


def normalize_price(
    price_text: Optional[str]
) -> float:
    if not price_text:

        raise ValueError(
            "price_text is missing"
        )

    cleaned = re.sub(
        r"[^0-9.]",
        "",
        price_text
    )

    if (
        not cleaned
        or cleaned.count(".") > 1
    ):

        raise ValueError(
            f"could not extract a numeric price "
            f"from {price_text!r}"
        )

    return float(cleaned)


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


def save_json(
    path: Path,
    data
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with path.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


def export_csv(
    records: list[dict],
    output_path: Path,
) -> None:
    fieldnames = [
        "title",
        "product_url",
        "price_text",
        "price_gbp",
        "availability_text",
        "rating_text",
        "description",
        "source_page",
        "fetched_at",
    ]

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with output_path.open(
        "w",
        encoding="utf-8",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for record in records:

            writer.writerow({
                field: record.get(field)
                for field in fieldnames
            })


CHANGE_FIELDS = [
    "title",
    "product_url",
    "price_text",
    "price_gbp",
    "availability_text",
    "rating_text",
    "description",
    "source_page",
]


def record_hash(record: dict) -> str:
    stable_data = {
        field: record.get(field)
        for field in CHANGE_FIELDS
    }

    canonical = json.dumps(
        stable_data,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def load_previous_books(
    path: Path
) -> Optional[list[dict]]:
    if not path.exists():
        return None

    try:

        with path.open(
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if not isinstance(data, list):
            return None

        return data

    except (
        OSError,
        json.JSONDecodeError
    ):

        return None


def calculate_changes(
    previous_records: Optional[list[dict]],
    current_records: list[dict],
) -> dict:
    if previous_records is None:

        return {
            "new": len(current_records),
            "changed": 0,
            "unchanged": 0,
            "gone": 0,
            "first_run": True,
        }

    previous_map = {
        str(record["product_url"]): record
        for record in previous_records
    }

    current_map = {
        str(record["product_url"]): record
        for record in current_records
    }

    new_count = 0
    changed_count = 0
    unchanged_count = 0
    gone_count = 0

    for url, current in current_map.items():

        if url not in previous_map:

            new_count += 1

            continue

        previous = previous_map[url]

        if (
            record_hash(previous)
            == record_hash(current)
        ):

            unchanged_count += 1

        else:

            changed_count += 1

    for url in previous_map:

        if url not in current_map:

            gone_count += 1

    return {
        "new": new_count,
        "changed": changed_count,
        "unchanged": unchanged_count,
        "gone": gone_count,
        "first_run": False,
    }


def format_price(
    value: Optional[float]
) -> str:
    if value is None:
        return "N/A"

    return f"£{value:.2f}"


def generate_dashboard(
    run_report: dict,
    change_report: dict,
    records: list[dict],
    output_path: Path,
) -> None:
    prices = [
        record["price_gbp"]
        for record in records
        if isinstance(
            record.get("price_gbp"),
            (int, float)
        )
    ]

    if prices:

        min_price = min(prices)
        max_price = max(prices)

    else:

        min_price = None
        max_price = None

    generated_at = datetime.now(
        timezone.utc
    ).isoformat()

    def esc(value) -> str:

        return html.escape(
            str(value)
        )

    dashboard = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Books Scraper Dashboard</title>

<style>
body {{
    font-family: Arial, sans-serif;
    margin: 40px;
    background: #f5f5f5;
    color: #222;
}}

h1 {{
    margin-bottom: 5px;
}}

.subtitle {{
    color: #666;
    margin-bottom: 30px;
}}

.grid {{
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
}}

.card {{
    background: white;
    padding: 22px;
    border-radius: 10px;
    box-shadow:
        0 2px 8px rgba(0,0,0,0.08);
}}

.label {{
    color: #666;
    font-size: 14px;
}}

.value {{
    font-size: 30px;
    font-weight: bold;
    margin-top: 8px;
}}

.section {{
    margin-top: 35px;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    background: white;
}}

td, th {{
    padding: 12px;
    border-bottom: 1px solid #ddd;
    text-align: left;
}}

th {{
    background: #eee;
}}
</style>
</head>

<body>

<h1>Books Scraper Dashboard</h1>

<div class="subtitle">
Generated: {esc(generated_at)}
</div>

<div class="grid">

<div class="card">
<div class="label">Valid Records</div>
<div class="value">
{run_report["valid_records"]}
</div>
</div>

<div class="card">
<div class="label">Discovered URLs</div>
<div class="value">
{run_report["discovered"]}
</div>
</div>

<div class="card">
<div class="label">Unique URLs</div>
<div class="value">
{run_report["unique_urls"]}
</div>
</div>

<div class="card">
<div class="label">Failed Pages</div>
<div class="value">
{run_report["failed_pages"]}
</div>
</div>

<div class="card">
<div class="label">Invalid Records</div>
<div class="value">
{run_report["invalid_records"]}
</div>
</div>

<div class="card">
<div class="label">Cache Hits</div>
<div class="value">
{run_report["cache_hits"]}
</div>
</div>

<div class="card">
<div class="label">Duration</div>
<div class="value">
{run_report["duration_seconds"]}s
</div>
</div>

</div>

<div class="section">

<h2>Price Range</h2>

<table>

<tr>
<th>Lowest Price</th>
<th>Highest Price</th>
</tr>

<tr>
<td>{esc(format_price(min_price))}</td>
<td>{esc(format_price(max_price))}</td>
</tr>

</table>

</div>


<div class="section">

<h2>Change Detection</h2>

<table>

<tr>
<th>New</th>
<th>Changed</th>
<th>Unchanged</th>
<th>Gone</th>
</tr>

<tr>
<td>{change_report["new"]}</td>
<td>{change_report["changed"]}</td>
<td>{change_report["unchanged"]}</td>
<td>{change_report["gone"]}</td>
</tr>

</table>

</div>


<div class="section">

<h2>Run Information</h2>

<table>

<tr>
<th>Field</th>
<th>Value</th>
</tr>

<tr>
<td>Catalogue pages</td>
<td>{run_report["catalogue_pages"]}</td>
</tr>

<tr>
<td>Detail pages</td>
<td>{run_report["detail_pages"]}</td>
</tr>

<tr>
<td>Pages fetched</td>
<td>{run_report["pages_fetched"]}</td>
</tr>

<tr>
<td>Cache hits</td>
<td>{run_report["cache_hits"]}</td>
</tr>

<tr>
<td>Started</td>
<td>{esc(run_report["start_time"])}</td>
</tr>

</table>

</div>

</body>
</html>
"""

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path.write_text(
        dashboard,
        encoding="utf-8"
    )


def main() -> None:
    stats = Stats()

    run_started_at = datetime.now(
        timezone.utc
    )

    run_start_perf = time.perf_counter()

    (
        catalogue_pages,
        book_link_pairs,
    ) = discover_catalogue_and_books(stats)

    discovered = len(
        book_link_pairs
    )

    unique_books: dict[str, str] = {}

    for url, source_page in book_link_pairs:

        if url not in unique_books:

            unique_books[url] = source_page

    unique_urls = len(
        unique_books
    )

    books_output_path = (
        OUTPUT_DIR / "books.json"
    )

    previous_records = load_previous_books(
        books_output_path
    )

    valid_records: list[BookRecord] = []

    invalid_records: list[dict] = []

    failed_pages: list[dict] = []

    for product_url, source_page in unique_books.items():

        cache_path = (
            CACHE_DIR
            / f"detail-{slugify_for_cache(product_url)}.html"
        )

        try:

            html_text = fetch_url(
                product_url,
                cache_path,
                stats
            )

        except FetchError as exc:

            failed_pages.append({
                "product_url": product_url,
                "reason": exc.reason,
            })

            continue

        fetched_at = datetime.now(
            timezone.utc
        ).isoformat()

        raw = None

        try:

            raw = extract_book(
                html_text,
                product_url,
                source_page,
                fetched_at,
            )

            price_gbp = normalize_price(
                raw["price_text"]
            )

            record = BookRecord(
                **raw,
                price_gbp=price_gbp,
            )

            valid_records.append(
                record
            )

        except (
            ValidationError,
            ValueError,
            TypeError,
        ) as exc:

            error_entry = (
                dict(raw)
                if raw
                else {
                    "product_url": product_url
                }
            )

            error_entry["error_reason"] = str(
                exc
            )

            invalid_records.append(
                error_entry
            )

    books_json = [
        json.loads(
            record.model_dump_json()
        )
        for record in valid_records
    ]

    change_report = calculate_changes(
        previous_records,
        books_json,
    )

    change_report["run_time"] = (
        run_started_at.isoformat()
    )

    change_report["current_records"] = len(
        books_json
    )

    change_report["previous_records"] = (
        len(previous_records)
        if previous_records is not None
        else 0
    )

    save_json(
        books_output_path,
        books_json
    )

    errors_json = {
        "invalid_records": invalid_records,
        "failed_pages": failed_pages,
    }

    save_json(
        OUTPUT_DIR / "errors.json",
        errors_json
    )

    export_csv(
        books_json,
        OUTPUT_DIR / "books.csv"
    )

    duration_seconds = round(
        time.perf_counter()
        - run_start_perf,
        3
    )

    run_report = {

        "start_time":
            run_started_at.isoformat(),

        "duration_seconds":
            duration_seconds,

        "catalogue_pages":
            len(catalogue_pages),

        "discovered":
            discovered,

        "unique_urls":
            unique_urls,

        "detail_pages":
            unique_urls,

        "pages_fetched":
            stats.pages_fetched,

        "cache_hits":
            stats.cache_hits,

        "valid_records":
            len(valid_records),

        "invalid_records":
            len(invalid_records),

        "failed_pages":
            len(failed_pages),

        "csv_exported":
            True,

        "change_detection":
            change_report,

        "dashboard":
            "output/dashboard.html",
    }

    save_json(
        OUTPUT_DIR / "run-report.json",
        run_report
    )

    save_json(
        OUTPUT_DIR / "change-report.json",
        change_report
    )

    generate_dashboard(
        run_report,
        change_report,
        books_json,
        OUTPUT_DIR / "dashboard.html",
    )

    print("\n--- run report ---")

    print(
        json.dumps(
            run_report,
            indent=2
        )
    )

    print("\n--- change report ---")

    print(
        json.dumps(
            change_report,
            indent=2
        )
    )

    print("\nExtras generated:")

    print("  output/books.csv")
    print("  output/change-report.json")
    print("  output/dashboard.html")


if __name__ == "__main__":
    main()