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


# =========================================================
# STAGE 5 — RUN TRACKING
# =========================================================

run_start = datetime.now(timezone.utc)

pages_fetched = 0
cache_hits = 0
failed_pages = 0


# =========================================================
# FETCH PAGE
# =========================================================

def get_page(url, cache_file):

    global pages_fetched
    global cache_hits
    global failed_pages

    # -----------------------------------------------------
    # Use cache if it already exists
    # -----------------------------------------------------

    if cache_file.exists():

        html = cache_file.read_text(encoding="utf-8-sig")

        cache_hits += 1

        print(f"CACHE {url} - {len(html)} bytes")

        return html

    # -----------------------------------------------------
    # Real request
    # -----------------------------------------------------

    print(f"FETCH {url}")

    for attempt in range(2):

        try:

            response = requests.get(
                url,
                headers=headers,
                timeout=10
            )

            # -------------------------------------------------
            # Success
            # -------------------------------------------------

            if response.status_code == 200:

                pages_fetched += 1

                response.encoding = response.apparent_encoding
                html = response.text

                cache_file.parent.mkdir(
                    parents=True,
                    exist_ok=True
                )

                cache_file.write_text(
                    html,
                    encoding="utf-8"
                )

                print(f"Response size: {len(html)} bytes")

                # Wait before another real request
                time.sleep(0.5)

                return html

            # -------------------------------------------------
            # 404 / 403
            # Do NOT retry
            # -------------------------------------------------

            if response.status_code in (403, 404):

                print(
                    f"Fetch failed: HTTP {response.status_code} "
                    f"(not retrying)"
                )

                failed_pages += 1

                return None

            # -------------------------------------------------
            # 5xx
            # Retry once
            # -------------------------------------------------

            if 500 <= response.status_code <= 599:

                print(
                    f"Fetch failed: HTTP {response.status_code}"
                )

                if attempt == 0:

                    print("Retrying once...")

                    time.sleep(1)

                    continue

                print("Retry failed.")

                failed_pages += 1

                return None

            # -------------------------------------------------
            # Other HTTP errors
            # -------------------------------------------------

            print(
                f"Fetch failed: HTTP {response.status_code}"
            )

            failed_pages += 1

            return None

        # -----------------------------------------------------
        # Timeout
        # Retry once
        # -----------------------------------------------------

        except requests.exceptions.Timeout:

            print("Request timed out.")

            if attempt == 0:

                print("Retrying once...")

                time.sleep(1)

                continue

            print("Retry failed.")

            failed_pages += 1

            return None

        # -----------------------------------------------------
        # Other request errors
        # -----------------------------------------------------

        except requests.exceptions.RequestException as e:

            print(f"Request error: {e}")

            failed_pages += 1

            return None

    return None


# =========================================================
# STAGE 2 — CATALOGUE
# =========================================================

catalogue_url = BASE_URL
catalogue_pages = 0
book_links = set()


while catalogue_url and catalogue_pages < 3:

    page_number = catalogue_pages + 1

    cache_file = (
        CACHE_DIR /
        f"catalogue-page-{page_number}.html"
    )

    html = get_page(
        catalogue_url,
        cache_file
    )

    if html is None:

        print(
            f"Skipping catalogue page: "
            f"{catalogue_url}"
        )

        catalogue_url = None
        continue

    catalogue_pages += 1

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # Find all book links

    for link in soup.select(
        "article.product_pod h3 a"
    ):

        href = link.get("href")

        if href:

            absolute_url = urljoin(
                catalogue_url,
                href
            )

            book_links.add(
                absolute_url
            )

    # Find catalogue Next link

    next_link = soup.select_one(
        "li.next a"
    )

    if next_link:

        catalogue_url = urljoin(
            catalogue_url,
            next_link.get("href")
        )

    else:

        catalogue_url = None


print(f"catalogue_pages={catalogue_pages}")
print(f"discovered={len(book_links)}")


# =========================================================
# STAGE 5 CHECKPOINT
# Add ONE fake URL intentionally
# =========================================================

fake_url = (
    BASE_URL +
    "catalogue/this-book-does-not-exist_9999/index.html"
)

book_links.add(fake_url)

print(f"Added fake URL: {fake_url}")
print(f"Total URLs to process: {len(book_links)}")


# =========================================================
# STAGE 3 — EXTRACT RAW BOOK RECORDS
# =========================================================

detail_cache_dir = CACHE_DIR / "details"

raw_records = []

# Keep track of which catalogue page each book came from

book_source_pages = {}


catalogue_url = BASE_URL
catalogue_pages_for_source = 0


while catalogue_url and catalogue_pages_for_source < 3:

    page_number = catalogue_pages_for_source + 1

    cache_file = (
        CACHE_DIR /
        f"catalogue-page-{page_number}.html"
    )

    html = get_page(
        catalogue_url,
        cache_file
    )

    if html is None:

        catalogue_pages_for_source += 1

        continue

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    for link in soup.select(
        "article.product_pod h3 a"
    ):

        href = link.get("href")

        if href:

            product_url = urljoin(
                catalogue_url,
                href
            )

            book_source_pages[
                product_url
            ] = catalogue_url

    next_link = soup.select_one(
        "li.next a"
    )

    if next_link:

        catalogue_url = urljoin(
            catalogue_url,
            next_link.get("href")
        )

    else:

        catalogue_url = None

    catalogue_pages_for_source += 1


# =========================================================
# Extract each unique book
# =========================================================

for product_url in sorted(book_links):

    # Create safe cache filename

    cache_name = (
        product_url
        .rstrip("/")
        .split("/")[-2]
        + ".html"
    )

    cache_file = (
        detail_cache_dir /
        cache_name
    )

    html = get_page(
        product_url,
        cache_file
    )

    # -----------------------------------------------------
    # IMPORTANT:
    # One failed page does NOT stop the whole run.
    # -----------------------------------------------------

    if html is None:

        print(
            f"SKIPPING FAILED PAGE: {product_url}"
        )

        continue

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # Product area only

    product_area = soup.select_one(
        "article.product_page"
    )

    if product_area is None:

        print(
            f"PRODUCT AREA NOT FOUND: "
            f"{product_url}"
        )

        continue

    # -----------------------------------------------------
    # Title
    # -----------------------------------------------------

    title_element = product_area.select_one(
        "h1"
    )

    title = (
        title_element.get_text(strip=True)
        if title_element
        else None
    )

    # -----------------------------------------------------
    # Price
    # -----------------------------------------------------

    price_element = product_area.select_one(
        ".price_color"
    )

    price_text = (
        price_element.get_text(strip=True)
        if price_element
        else None
    )

    # -----------------------------------------------------
    # Availability
    # -----------------------------------------------------

    availability_element = (
        product_area.select_one(
            ".availability"
        )
    )

    availability_text = (
        availability_element.get_text(
            " ",
            strip=True
        )
        if availability_element
        else None
    )

    # -----------------------------------------------------
    # Rating
    # -----------------------------------------------------

    rating_element = product_area.select_one(
        "p.star-rating"
    )

    if rating_element:

        rating_classes = rating_element.get(
            "class",
            []
        )

        rating_text = next(
            (
                cls
                for cls in rating_classes
                if cls != "star-rating"
            ),
            None
        )

    else:

        rating_text = None

    # -----------------------------------------------------
    # Description
    # -----------------------------------------------------

    description_element = (
        product_area.select_one(
            "#product_description + p"
        )
    )

    description = (
        description_element.get_text(
            " ",
            strip=True
        )
        if description_element
        else None
    )

    # -----------------------------------------------------
    # Provenance
    # -----------------------------------------------------

    source_page = book_source_pages.get(
        product_url
    )

    fetched_at = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    record = {

        "title": title,

        "product_url": product_url,

        "price_text": price_text,

        "availability_text": (
            availability_text
        ),

        "rating_text": rating_text,

        "description": description,

        "source_page": source_page,

        "fetched_at": fetched_at
    }

    raw_records.append(record)


# =========================================================
# CHECKPOINT
# =========================================================

print("\n--- ONE COMPLETE RAW RECORD ---")

if raw_records:

    print(raw_records[0])

else:

    print("No records extracted.")


print("\n--- STAGE 3 SUMMARY ---")

print(
    f"Records extracted: "
    f"{len(raw_records)}"
)

print(
    f"Unique product URLs: "
    f"{len(book_links)}"
)

print(
    f"Records with description: "
    f"{sum(r['description'] is not None for r in raw_records)}"
)

print(
    f"Records without description: "
    f"{sum(r['description'] is None for r in raw_records)}"
)


# =========================================================
# STAGE 4 — VALIDATION
# =========================================================

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


# =========================================================
# Output directory
# =========================================================

OUTPUT_DIR = Path("output")

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


books_file = (
    OUTPUT_DIR /
    "books.json"
)

errors_file = (
    OUTPUT_DIR /
    "errors.json"
)


valid_books = []

errors = []

seen_urls = set()


# =========================================================
# Normalize + validate
# =========================================================

for raw in raw_records:

    try:

        # URL

        product_url = raw.get(
            "product_url"
        )

        if not product_url:

            raise ValueError(
                "Missing product_url"
            )

        product_url = (
            product_url
            .strip()
            .rstrip("/")
        )

        # Duplicate check

        if product_url in seen_urls:

            continue

        # Price

        price_text = raw.get(
            "price_text"
        )

        if not price_text:

            raise ValueError(
                "Missing price_text"
            )

        clean_price = (
            price_text
            .replace("£", "")
            .strip()
        )

        price_gbp = float(
            clean_price
        )

        # Normalized record

        normalized_record = {

            "title": raw.get("title"),

            "product_url": product_url,

            "price_text": price_text,

            "price_gbp": price_gbp,

            "availability_text": (
                raw.get(
                    "availability_text"
                )
            ),

            "rating_text": (
                raw.get(
                    "rating_text"
                )
            ),

            "description": (
                raw.get(
                    "description"
                )
            ),

            "source_page": (
                raw.get(
                    "source_page"
                )
            ),

            "fetched_at": (
                raw.get(
                    "fetched_at"
                )
            )
        }

        # Validate

        book = Book.model_validate(
            normalized_record
        )

        valid_books.append(
            book.model_dump(
                mode="json"
            )
        )

        seen_urls.add(
            product_url
        )

    except (
        ValueError,
        ValidationError,
        TypeError
    ) as e:

        errors.append({

            "record": raw,

            "reason": str(e)
        })


# =========================================================
# Save books.json
# =========================================================

with books_file.open(
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        valid_books,
        f,
        indent=2,
        ensure_ascii=False
    )


# =========================================================
# Save errors.json
# =========================================================

with errors_file.open(
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        errors,
        f,
        indent=2,
        ensure_ascii=False
    )


# =========================================================
# STAGE 5 — RUN REPORT
# =========================================================

run_end = datetime.now(
    timezone.utc
)

duration = (
    run_end - run_start
).total_seconds()


run_report = {

    "start_time": run_start.isoformat(),

    "duration_seconds": duration,

    "pages_fetched": pages_fetched,

    "cache_hits": cache_hits,

    "valid_records": len(valid_books),

    "invalid_records": len(errors),

    "failed_pages": failed_pages
}


run_report_file = (
    OUTPUT_DIR /
    "run-report.json"
)


with run_report_file.open(
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        run_report,
        f,
        indent=2
    )


# =========================================================
# FINAL SUMMARY
# =========================================================

print("\n--- STAGE 5 SUMMARY ---")

print(
    f"Valid records: "
    f"{len(valid_books)}"
)

print(
    f"Rejected records: "
    f"{len(errors)}"
)

print(
    f"Unique valid URLs: "
    f"{len(seen_urls)}"
)

print(
    f"Pages fetched: "
    f"{pages_fetched}"
)

print(
    f"Cache hits: "
    f"{cache_hits}"
)

print(
    f"Failed pages: "
    f"{failed_pages}"
)

print(
    f"Saved to: "
    f"{books_file}"
)

print(
    f"Errors saved to: "
    f"{errors_file}"
)

print(
    f"Run report saved to: "
    f"{run_report_file}"
)

print(
    f"Duration: "
    f"{duration:.2f} seconds"
)