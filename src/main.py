import requests
import time
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timezone

BASE_URL = "https://books.toscrape.com/"
CACHE_DIR = Path("cache")

headers = {
    "User-Agent": "FlyRankInternship A9/1.0 (+https://github.com/urviporwal129/scraper)"
}


def get_page(url, cache_file):
    # Use cache if it already exists
    if cache_file.exists():
        html = cache_file.read_text(encoding="utf-8-sig")
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
    response.encoding = response.apparent_encoding
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

# =========================
# STAGE 3 — EXTRACT RAW BOOK RECORDS
# =========================

detail_cache_dir = CACHE_DIR / "details"
raw_records = []

# Keep track of which catalogue page each book came from
# so source_page can be preserved as provenance.
book_source_pages = {}

catalogue_url = BASE_URL
catalogue_pages_for_source = 0

while catalogue_url and catalogue_pages_for_source < 3:

    page_number = catalogue_pages_for_source + 1
    cache_file = CACHE_DIR / f"catalogue-page-{page_number}.html"

    html = get_page(catalogue_url, cache_file)

    if html is None:
        break

    soup = BeautifulSoup(html, "html.parser")

    for link in soup.select("article.product_pod h3 a"):
        href = link.get("href")

        if href:
            product_url = urljoin(catalogue_url, href)
            book_source_pages[product_url] = catalogue_url

    next_link = soup.select_one("li.next a")

    if next_link:
        catalogue_url = urljoin(catalogue_url, next_link.get("href"))
    else:
        catalogue_url = None

    catalogue_pages_for_source += 1


# Extract each unique book
for product_url in sorted(book_links):

    # Create a safe cache filename from the product URL
    cache_name = product_url.rstrip("/").split("/")[-1] + ".html"
    cache_file = detail_cache_dir / cache_name

    html = get_page(product_url, cache_file)

    if html is None:
        continue

    soup = BeautifulSoup(html, "html.parser")

    # Product area only
    product_area = soup.select_one("article.product_page")

    if product_area is None:
        print(f"PRODUCT AREA NOT FOUND: {product_url}")
        continue

    # Title
    title_element = product_area.select_one("h1")
    title = title_element.get_text(strip=True) if title_element else None

    # Price
    price_element = product_area.select_one(".price_color")
    price_text = price_element.get_text(strip=True) if price_element else None

    # Availability
    availability_element = product_area.select_one(".availability")
    availability_text = (
        availability_element.get_text(" ", strip=True)
        if availability_element
        else None
    )

    # Rating
    rating_element = product_area.select_one("p.star-rating")

    if rating_element:
        rating_classes = rating_element.get("class", [])
        rating_text = next(
            (cls for cls in rating_classes if cls != "star-rating"),
            None
        )
    else:
        rating_text = None

    # Description
    description_element = product_area.select_one("#product_description + p")

    description = (
        description_element.get_text(" ", strip=True)
        if description_element
        else None
    )

    description = (
        description_element.get_text(strip=True)
        if description_element
        else None
    )

    # Provenance
    source_page = book_source_pages.get(product_url)

    fetched_at = datetime.now(timezone.utc).isoformat()

    record = {
        "title": title,
        "product_url": product_url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": fetched_at
    }

    raw_records.append(record)


# =========================
# CHECKPOINT
# =========================

print("\n--- ONE COMPLETE RAW RECORD ---")

if raw_records:
    print(raw_records[0])
else:
    print("No records extracted.")

print("\n--- STAGE 3 SUMMARY ---")
print(f"Records extracted: {len(raw_records)}")
print(f"Unique product URLs: {len(book_links)}")
print(
    f"Records with description: "
    f"{sum(r['description'] is not None for r in raw_records)}"
)
print(
    f"Records without description: "
    f"{sum(r['description'] is None for r in raw_records)}"
)
