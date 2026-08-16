from pathlib import Path
from urllib.parse import urljoin
import time

import requests
from bs4 import BeautifulSoup


START_URL = "https://books.toscrape.com/catalogue/page-1.html"

CACHE_DIR = Path("cache/catalogue")

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
    global last_request_time

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
        f"FETCHED | {url} | "
        f"status={response.status_code} | size={len(html)} bytes"
    )

    return html


def get_cache_file(page_number):
    return CACHE_DIR / f"page-{page_number}.html"


def extract_book_urls(html, page_url):
    soup = BeautifulSoup(html, "html.parser")

    urls = []

    for link in soup.select("article.product_pod h3 a"):
        href = link.get("href")

        if href:
            absolute_url = urljoin(page_url, href)
            urls.append(absolute_url)

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
        cache_file = get_cache_file(page_number)

        html = fetch_page(current_url, cache_file)

        catalogue_pages.append(current_url)

        book_urls = extract_book_urls(html, current_url)
        all_book_urls.extend(book_urls)

        print(
            f"PAGE {page_number} | "
            f"books={len(book_urls)}"
        )

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


def main():
    discover_books()


if __name__ == "__main__":
    main()