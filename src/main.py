import requests
import time
import json
from pydantic import BaseModel, HttpUrl, ValidationError
from typing import Optional

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
    cache_name = product_url.rstrip("/").split("/")[-2] + ".html"
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

class Book(BaseModel):
    title: str
    product_url: HttpUrl
    price_text: str
    price_gbp: float
    availability_text: Optional[str] = None
    rating_text: Optional[str] = None
    description: Optional[str] = None
    source_page: Optional[HttpUrl] = None
    fetched_at: str


# -------------------------
# Output directory
# -------------------------

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

books_file = OUTPUT_DIR / "books.json"
errors_file = OUTPUT_DIR / "errors.json"


valid_books = []
errors = []

# Product URL is the identity
seen_urls = set()


# -------------------------
# Normalize + validate
# -------------------------

for raw in raw_records:

    try:
        # Get URL
        product_url = raw.get("product_url")

        if not product_url:
            raise ValueError("Missing product_url")

        # Normalize URL for deduplication
        product_url = product_url.strip().rstrip("/")

        # Skip duplicate books
        if product_url in seen_urls:
            continue

        # Price
        price_text = raw.get("price_text")

        if not price_text:
            raise ValueError("Missing price_text")

        clean_price = price_text.replace("£", "").strip()
        price_gbp = float(clean_price)

        # Normalized record
        normalized_record = {
            "title": raw.get("title"),
            "product_url": product_url,
            "price_text": price_text,
            "price_gbp": price_gbp,
            "availability_text": raw.get("availability_text"),
            "rating_text": raw.get("rating_text"),
            "description": raw.get("description"),
            "source_page": raw.get("source_page"),
            "fetched_at": raw.get("fetched_at")
        }

        # Validate
        book = Book.model_validate(normalized_record)

        # Store only after successful validation
        valid_books.append(book.model_dump(mode="json"))

        # Mark URL as already stored
        seen_urls.add(product_url)

    except (ValueError, ValidationError, TypeError) as e:

        errors.append({
            "record": raw,
            "reason": str(e)
        })


# -------------------------
# Save books
# -------------------------

with books_file.open("w", encoding="utf-8") as f:
    json.dump(valid_books, f, indent=2, ensure_ascii=False)


# -------------------------
# Save errors
# -------------------------

with errors_file.open("w", encoding="utf-8") as f:
    json.dump(errors, f, indent=2, ensure_ascii=False)


# -------------------------
# CHECKPOINT
# -------------------------

print("\n--- STAGE 4 SUMMARY ---")
print(f"Valid records: {len(valid_books)}")
print(f"Rejected records: {len(errors)}")
print(f"Unique URLs: {len(seen_urls)}")
print(f"Saved to: {books_file}")
print(f"Errors saved to: {errors_file}")

