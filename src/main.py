import requests
import time
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://books.toscrape.com/"
CACHE_DIR = Path("cache")

headers = {
    "User-Agent": "FlyRankInternship A9/1.0 (+https://github.com/urviporwal129/scraper)"
}


def get_page(url, cache_file):
    # Use cache if it already exists
    if cache_file.exists():
        html = cache_file.read_text(encoding="utf-8")
        print(f"CACHE {url} - {len(html)} bytes")
        return html

    # Real request
    print(f"FETCH {url}")

    response = requests.get(
        url,
        headers=headers,
        timeout=10
    )

    if response.status_code != 200:
        print(f"Fetch failed: HTTP {response.status_code}")
        return None

    html = response.text

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(html, encoding="utf-8")

    print(f"Response size: {len(html)} bytes")

    # Wait before another real request
    time.sleep(0.5)

    return html


catalogue_url = BASE_URL
catalogue_pages = 0
book_links = set()

while catalogue_url and catalogue_pages < 3:

    # Page number for cache filename
    page_number = catalogue_pages + 1
    cache_file = CACHE_DIR / f"catalogue-page-{page_number}.html"

    html = get_page(catalogue_url, cache_file)

    if html is None:
        break

    catalogue_pages += 1

    soup = BeautifulSoup(html, "html.parser")

    # Find all book links
    for link in soup.select("article.product_pod h3 a"):
        href = link.get("href")

        if href:
            absolute_url = urljoin(catalogue_url, href)
            book_links.add(absolute_url)

    # Find the catalogue's Next link
    next_link = soup.select_one("li.next a")

    if next_link:
        catalogue_url = urljoin(catalogue_url, next_link.get("href"))
    else:
        catalogue_url = None


print(f"catalogue_pages={catalogue_pages}")
print(f"discovered={len(book_links)}")