from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime, timezone
import hashlib
import time

import requests
from bs4 import BeautifulSoup


START_URL = "https://books.toscrape.com/catalogue/page-1.html"

CATALOGUE_CACHE_DIR = Path("cache/catalogue")
BOOK_CACHE_DIR = Path("cache/books")

USER_AGENT = "FlyRankInternshipA9/1.0"
TIMEOUT = 10
REQUEST_DELAY = 0.5

last_request_time = 0


def wait_before_request():
    global last_request_time

    if last_request_time:
        elapsed = time.monotonic() - last_request_time

        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)

    last_request_time = time.monotonic()


def fetch_page(url, cache_file):
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    if cache_file.exists():
        html = cache_file.read_text(encoding="utf-8")
        print(f"CACHE HIT | {url} | size={len(html)} bytes")
        return html

    wait_before_request()

    print(f"FETCH | {url}")

    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT
        )
    except requests.RequestException as error:
        raise RuntimeError(f"Request failed: {error}")

    if response.status_code != 200:
        raise RuntimeError(
            f"Request failed: HTTP {response.status_code}"
        )

    html = response.text

    cache_file.write_text(html, encoding="utf-8")

    print(
        f"FETCHED | status={response.status_code} | "
        f"size={len(html)} bytes"
    )

    return html


def get_cache_file(directory, url):
    name = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return directory / f"{name}.html"


def extract_book_urls(html, page_url):
    soup = BeautifulSoup(html, "html.parser")

    urls = []

    for link in soup.select("article.product_pod h3 a"):
        href = link.get("href")

        if href:
            urls.append(urljoin(page_url, href))

    return urls


def get_next_url(html, current_url):
    soup = BeautifulSoup(html, "html.parser")

    next_link = soup.select_one("li.next a")

    if not next_link:
        return None

    href = next_link.get("href")

    if not href:
        return None

    return urljoin(current_url, href)


def discover_books():
    current_url = START_URL
    catalogue_pages = []
    all_book_urls = []

    for page_number in range(1, 4):
        cache_file = CATALOGUE_CACHE_DIR / f"page-{page_number}.html"

        html = fetch_page(current_url, cache_file)

        catalogue_pages.append(current_url)

        book_urls = extract_book_urls(html, current_url)
        all_book_urls.extend(book_urls)

        if page_number == 3:
            break

        next_url = get_next_url(html, current_url)

        if not next_url:
            raise RuntimeError(
                f"Next page was not found after {current_url}"
            )

        current_url = next_url

    unique_urls = list(dict.fromkeys(all_book_urls))

    print()
    print(f"catalogue_pages={len(catalogue_pages)}")
    print(f"discovered={len(all_book_urls)}")
    print(f"unique_urls={len(unique_urls)}")

    return catalogue_pages, unique_urls


def extract_text(element):
    if element is None:
        return None

    text = element.get_text(" ", strip=True)

    return text if text else None


def extract_description(soup):
    heading = soup.select_one("#product_description")

    if not heading:
        return None

    paragraph = heading.find_next_sibling("p")

    return extract_text(paragraph)


def extract_rating(soup):
    rating = soup.select_one("p.star-rating")

    if not rating:
        return None

    classes = rating.get("class", [])

    rating_names = {
        "One",
        "Two",
        "Three",
        "Four",
        "Five"
    }

    for class_name in classes:
        if class_name in rating_names:
            return class_name

    return None


def extract_book(html, product_url, source_page):
    soup = BeautifulSoup(html, "html.parser")

    product_area = soup.select_one("div.product_main")

    if not product_area:
        raise ValueError("Product area was not found")

    title = extract_text(product_area.select_one("h1"))
    price_text = extract_text(product_area.select_one("p.price_color"))
    availability_text = extract_text(product_area.select_one("p.instock"))
    rating_text = extract_rating(product_area)
    description = extract_description(soup)

    if not title:
        raise ValueError("Book title was not found")

    if not price_text:
        raise ValueError("Book price was not found")

    fetched_at = datetime.now(timezone.utc).isoformat()

    return {
        "title": title,
        "product_url": product_url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": fetched_at
    }


def scrape_books(book_urls, catalogue_pages):
    records = []

    for index, product_url in enumerate(book_urls, start=1):
        source_page = catalogue_pages[(index - 1) // 20]

        cache_file = get_cache_file(BOOK_CACHE_DIR, product_url)

        html = fetch_page(product_url, cache_file)

        record = extract_book(
            html,
            product_url,
            source_page
        )

        records.append(record)

        print(
            f"BOOK {index}/{len(book_urls)} | "
            f"{record['title']}"
        )

    return records


def main():
    catalogue_pages, book_urls = discover_books()

    records = scrape_books(
        book_urls,
        catalogue_pages
    )

    print()
    print(f"detail_pages={len(records)}")
    print()
    print(records[0])


if __name__ == "__main__":
    main()