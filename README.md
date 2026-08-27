# Scraper

## Target classification

* **Target:** Books to Scrape (https://books.toscrape.com/)
* **Why:** It is a sandbox website created for practicing web scraping.
* **Scope:** The first 3 catalogue pages only.
* **Data collected:** Book title, price, availability, and rating.
* **Why this is appropriate:** The site is specifically provided as a safe sandbox for practicing web scraping, and the scraping scope is limited to the first 3 catalogue pages.
* **robots.txt result:** No robots file found (the URL returned 404 Not Found).
* I will not reuse this code on another site without checking its rules and terms first.

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Run

Run the scraper with:

```bash
python src/main.py
```

The scraper produces:

* `output/books.json` — collected book records
* `output/run-report.json` — report from the scraper run
* `output/errors.json` — recorded errors, if any

## Scraping lane

This project uses the HTTP/HTML scraping lane. The scraper requests the server-rendered HTML and extracts the required information from it.

## Raw record schema

Each raw book record contains:

* `title` — book title collected from the page
* `price` — book price collected from the page
* `availability` — availability information collected from the page
* `rating` — book rating collected from the page
* `url` — source book URL

## Politeness rules

- **User-Agent:** `FlyRankInternship A9/1.0 (+https://github.com/urviporwal129/scraper)`
- **Request delay:** 0.5 seconds between requests.
- **Timeout:** 10 seconds per request.
- **Caching:** Downloaded HTML pages are cached locally in `cache/` to avoid unnecessary repeat requests.
- **Retry behavior:** Failed requests are retried once where applicable. Timeout errors are also retried once, with a 1-second delay before the retry.

The `cache/` directory is excluded from Git using `.gitignore`.

## Limitation

The scraper depends on the current HTML structure of Books to Scrape. If the site's HTML structure changes, the extraction logic may need to be updated.

## Browser decision

This assignment did not need a browser because the data is already in the HTML the server sends, so a browser would only add cost.

## Ethics

I use an official API when one exists, never bypass logins, paywalls, or blocks, and collect only the data needed for the assignment.

## Sample run report

```json

{
  "start_time": "2026-08-27T07:20:07.373384+00:00",
  "duration_seconds": 5.755323,
  "pages_fetched": 0,
  "cache_hits": 66,
  "valid_records": 60,
  "invalid_records": 0,
  "failed_pages": 1
}

```

