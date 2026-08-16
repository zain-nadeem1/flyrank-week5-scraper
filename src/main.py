from pathlib import Path
import time

import requests


BASE_URL = "https://books.toscrape.com/catalogue/page-1.html"
CACHE_FILE = Path("cache/catalogue-page-1.html")

USER_AGENT = "FlyRankInternshipA9/1.0"
TIMEOUT = 10


def fetch_page(url):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    if CACHE_FILE.exists():
        html = CACHE_FILE.read_text(encoding="utf-8")
        print(f"CACHE HIT | status=200 | size={len(html)} bytes")
        return html

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
        raise RuntimeError(f"Request failed with status {response.status_code}")

    html = response.text
    CACHE_FILE.write_text(html, encoding="utf-8")

    print(f"FETCHED | status={response.status_code} | size={len(html)} bytes")

    return html


def main():
    fetch_page(BASE_URL)


if __name__ == "__main__":
    main()