import asyncio
import random
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any

USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
]

async def scrape_site(site: str, query: str, delay: float = 2.0) -> List[Dict[str, Any]]:
    headers = {"User-Agent": random.choice(USER_AGENTS), "Accept-Language": "en-US,en;q=0.9"}
    base_urls = {
        "amazon": f"https://www.amazon.com/s?k={query}",
        "ebay": f"https://www.ebay.com/sch/i.html?_nkw={query}",
        "swappa": f"https://swappa.com/search?q={query}"
    }
    url = base_urls.get(site)
    if not url:
        return []

    async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            await asyncio.sleep(delay)  # FIXED: Non-blocking async delay
            return parse_results(soup, site)
        except httpx.HTTPError as e:
            print(f"[{site}] Request failed: {e}")
            return []

def parse_results(soup: BeautifulSoup, site: str) -> List[Dict[str, Any]]:
    results = []
    if site == "amazon":
        for card in soup.select("div[data-component-type='s-search-result']")[:10]:
            title = card.select_one("h2 a span")
            price = card.select_one("span.a-price-whole")
            url = card.select_one("h2 a")
            if title and price and url:
                results.append({
                    "title": title.text.strip(),
                    "price": price.parent.find_next_sibling("span").text.strip(),
                    "url": "https://www.amazon.com" + url.get("href", "")
                })
    elif site == "ebay":
        for item in soup.select("div.s-item__wrapper")[:10]:
            title = item.select_one("div.s-item__title span")
            price = item.select_one("span.s-item__price")
            link = item.select_one("a.s-item__link")
            if title and price and link:
                results.append({
                    "title": title.text.strip(),
                    "price": price.text.strip(),
                    "url": link.get("href", "").split("?")[0]
                })
    elif site == "swappa":
        for card in soup.select("div.product-card")[:10]:
            title = card.select_one("h3 a")
            price = card.select_one("span.price")
            link = card.select_one("h3 a")
            if title and price and link:
                results.append({
                    "title": title.text.strip(),
                    "price": price.text.strip(),
                    "url": link.get("href", "").split("?")[0]
                })
    return results
