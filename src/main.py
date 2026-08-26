import requests
from pathlib import Path

URL = "https://books.toscrape.com/"
CACHE_FILE = Path("cache/catalogue-page-1.html")

headers = {
    "User-Agent": "FlyRankInternship A9/1.0 (+https://github.com/urviporwal129/scraper)"
}

if CACHE_FILE.exists():
    html = CACHE_FILE.read_text(encoding="utf-8")
    print("CACHE")
    print(f"Response size: {len(html)} bytes")

else:
    print("FETCH")

    response = requests.get(
        URL,
        headers=headers,
        timeout=10
    )

    if response.status_code != 200:
        print(f"Fetch failed: HTTP {response.status_code}")
        exit()

    html = response.text

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(html, encoding="utf-8")

    print(f"Response size: {len(html)} bytes")