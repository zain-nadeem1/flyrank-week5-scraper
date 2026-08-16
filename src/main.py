import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, HttpUrl, ValidationError


BASE_URL = "https://books.toscrape.com/"
CATALOGUE_URL = "https://books.toscrape.com/catalogue/page-1.html"

CACHE_DIR = Path("cache")
OUTPUT_DIR = Path("output")

CACHE_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

USER_AGENT = "FlyRankInternshipA9/1.0 (+https://github.com/yourusername/yourrepo)"
TIMEOUT = 10
DELAY = 0.5


class BookRecord(BaseModel):
    title: str
    product_url: HttpUrl
    price_text: str
    price_gbp: float
    availability_text: str
    rating_text: str
    description: str | None
    source_page: HttpUrl
    fetched_at: str


def clean_text(text):
    if text is None:
        return None

    return " ".join(text.split()).strip()


def fix_encoding(text):
    if text is None:
        return None

    replacements = {
        "Ã‚Â£": "£",
        "Â£": "£",
        "Ã‚": "",
        "Â": "",
        "Ã©": "é",
        "Ã¨": "è",
        "Ãª": "ê",
        "Ã´": "ô",
        "Ã¶": "ö",
        "Ã¼": "ü",
        "Ã±": "ñ",
        "â": "’",
        "â": "–",
        "â": "—",
        "â": "“",
        "â": "”",
        "â¦": "…",
        "â": "‘",
        "â¢": "•",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def fetch_page(url, cache_file):
    if cache_file.exists():
        content = cache_file.read_text(encoding="utf-8")
        print(f"CACHE HIT | {url} | size={len(content.encode('utf-8'))} bytes")
        return content, True

    headers = {
        "User-Agent": USER_AGENT
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=TIMEOUT
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"HTTP {response.status_code} for {url}"
        )

    response.encoding = "utf-8"
    content = response.text

    cache_file.write_text(
        content,
        encoding="utf-8"
    )

    print(f"FETCH | {url} | status={response.status_code} | size={len(response.content)} bytes")

    return content, False


def normalize_price(price_text):
    price_text = fix_encoding(price_text)
    price_text = price_text.replace("£", "").strip()

    return float(price_text)


def extract_book(html, product_url, source_page):
    soup = BeautifulSoup(html, "html.parser")

    product = soup.select_one("article.product_page")

    if product is None:
        raise ValueError("Product page section not found")

    title_element = product.select_one("h1")

    price_element = product.select_one("p.price_color")

    availability_element = product.select_one(
        "p.availability"
    )

    rating_element = product.select_one(
        "p.star-rating"
    )

    description_element = soup.select_one(
        "#product_description + p"
    )

    if title_element is None:
        raise ValueError("Title not found")

    if price_element is None:
        raise ValueError("Price not found")

    if availability_element is None:
        raise ValueError("Availability not found")

    title = clean_text(
        fix_encoding(title_element.get_text())
    )

    price_text = clean_text(
        fix_encoding(price_element.get_text())
    )

    availability_text = clean_text(
        fix_encoding(availability_element.get_text())
    )

    rating_text = None

    if rating_element is not None:
        classes = rating_element.get("class", [])

        rating_names = {
            "One",
            "Two",
            "Three",
            "Four",
            "Five"
        }

        for item in classes:
            if item in rating_names:
                rating_text = item
                break

    if description_element is not None:
        description = clean_text(
            fix_encoding(description_element.get_text())
        )
    else:
        description = None

    fetched_at = datetime.now(
        timezone.utc
    ).isoformat()

    return {
        "title": title,
        "product_url": product_url,
        "price_text": price_text,
        "price_gbp": normalize_price(price_text),
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": fetched_at
    }


def validate_record(record):
    return BookRecord.model_validate(record)


def save_json(path, data):
    with path.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )


def main():
    start_time = time.time()

    fetched_pages = 0
    cache_hits = 0
    failed_pages = 0

    catalogue_url = CATALOGUE_URL
    catalogue_pages = []

    first_cache = CACHE_DIR / "catalogue-page-1.html"

    html, cached = fetch_page(
        catalogue_url,
        first_cache
    )

    if cached:
        cache_hits += 1
    else:
        fetched_pages += 1

    current_html = html
    current_url = catalogue_url

    for page_number in range(1, 4):
        catalogue_pages.append(
            (current_url, current_html)
        )

        soup = BeautifulSoup(
            current_html,
            "html.parser"
        )

        next_link = soup.select_one(
            "li.next a"
        )

        if page_number == 3:
            break

        if next_link is None:
            raise RuntimeError(
                f"Next page not found after page {page_number}"
            )

        next_url = urljoin(
            current_url,
            next_link.get("href")
        )

        cache_file = CACHE_DIR / f"catalogue-page-{page_number + 1}.html"

        if not cache_file.exists():
            time.sleep(DELAY)

        current_html, cached = fetch_page(
            next_url,
            cache_file
        )

        if cached:
            cache_hits += 1
        else:
            fetched_pages += 1

        current_url = next_url

    book_urls = []

    source_pages = {}

    for page_url, page_html in catalogue_pages:
        soup = BeautifulSoup(
            page_html,
            "html.parser"
        )

        for link in soup.select(
            "article.product_pod h3 a"
        ):
            href = link.get("href")

            if not href:
                continue

            product_url = urljoin(
                page_url,
                href
            )

            if product_url not in source_pages:
                source_pages[product_url] = page_url
                book_urls.append(product_url)

    book_urls = list(
        dict.fromkeys(book_urls)
    )

    print(
        f"catalogue_pages={len(catalogue_pages)}"
    )

    print(
        f"discovered={len(book_urls)}"
    )

    print(
        f"unique_urls={len(book_urls)}"
    )

    valid_records = []
    invalid_records = []

    for index, product_url in enumerate(
        book_urls,
        start=1
    ):
        cache_name = (
            product_url
            .replace("https://books.toscrape.com/catalogue/", "")
            .replace("/", "_")
            .replace(":", "_")
        )

        cache_file = CACHE_DIR / f"{cache_name}.html"

        try:
            if not cache_file.exists():
                time.sleep(DELAY)

            html, cached = fetch_page(
                product_url,
                cache_file
            )

            if cached:
                cache_hits += 1
            else:
                fetched_pages += 1

            raw_record = extract_book(
                html,
                product_url,
                source_pages[product_url]
            )

            print(
                f"BOOK {index}/{len(book_urls)} | {raw_record['title']}"
            )

            try:
                validated = validate_record(
                    raw_record
                )

                valid_records.append(
                    validated.model_dump(
                        mode="json"
                    )
                )

            except ValidationError as error:
                invalid_records.append(
                    {
                        "product_url": product_url,
                        "reason": str(error),
                        "record": raw_record
                    }
                )

        except Exception as error:
            failed_pages += 1

            print(
                f"FAILED | {product_url} | {error}"
            )

    save_json(
        OUTPUT_DIR / "books.json",
        valid_records
    )

    save_json(
        OUTPUT_DIR / "errors.json",
        invalid_records
    )

    duration = time.time() - start_time

    report = {
        "started_at": datetime.fromtimestamp(
            start_time,
            timezone.utc
        ).isoformat(),
        "duration_seconds": round(
            duration,
            2
        ),
        "catalogue_pages": len(
            catalogue_pages
        ),
        "detail_pages": len(
            book_urls
        ),
        "pages_fetched": fetched_pages,
        "cache_hits": cache_hits,
        "valid_records": len(
            valid_records
        ),
        "invalid_records": len(
            invalid_records
        ),
        "failed_pages": failed_pages
    }

    save_json(
        OUTPUT_DIR / "run-report.json",
        report
    )

    print()
    print(
        f"valid_records={len(valid_records)}"
    )
    print(
        f"invalid_records={len(invalid_records)}"
    )


if __name__ == "__main__":
    main()