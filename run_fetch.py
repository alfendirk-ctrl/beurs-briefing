"""
Tijdelijke fetch zonder feedparser — gebruikt stdlib xml + requests + bs4.
"""

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

MARKET_FEEDS = [
    ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("Reuters",     "https://feeds.reuters.com/reuters/businessNews"),
    ("Google News", "https://news.google.com/rss/search?q=stock+market&hl=en-US&gl=US&ceid=US:en"),
]

MARKET_KEYWORDS = re.compile(
    r"\b(fed|federal reserve|inflation|nasdaq|s&p|earnings|rate hike|interest rate|"
    r"gdp|recession|cpi|pce|jobs report|unemployment|fomc|powell|treasury|yield)\b",
    re.IGNORECASE,
)

MATERIAL_KEYWORDS = re.compile(
    r"\b(earnings beat|earnings miss|beat estimates|missed estimates|"
    r"upgrade|downgrade|merger|acquisition|acqui|ceo|chief executive|"
    r"guidance raised|guidance lowered|raised guidance|lowered guidance|"
    r"sec investigation|sec charges|dividend cut|dividend raise|raised dividend|"
    r"buyback|share repurchase|revenue beat|revenue miss)\b",
    re.IGNORECASE,
)

MAX_MARKET_ITEMS = 3
MAX_TICKER_ITEMS = 3
HEADERS = {"User-Agent": "beurs-briefing/1.0"}


def fetch_rss(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = []
        for item in root.iter("item"):
            def t(tag):
                el = item.find(tag)
                return el.text or "" if el is not None else ""
            items.append({"title": t("title"), "summary": t("description"), "link": t("link"), "published": t("pubDate")})
        return items
    except Exception as e:
        print(f"  [WARN] {url}: {e}")
        return []


def clean(raw):
    text = BeautifulSoup(raw or "", "html.parser").get_text(" ", strip=True)
    return text[:280].strip()


def get_market_news():
    results, seen = [], set()
    for source, url in MARKET_FEEDS:
        if len(results) >= MAX_MARKET_ITEMS:
            break
        for e in fetch_rss(url):
            if len(results) >= MAX_MARKET_ITEMS:
                break
            t = e["title"].strip()
            if t in seen:
                continue
            if MARKET_KEYWORDS.search(e["title"] + " " + e["summary"]):
                seen.add(t)
                results.append({"title": t, "summary": clean(e["summary"]), "source": source, "link": e["link"], "published": e["published"]})
    return results


def get_ticker_news(ticker):
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    results = []
    for e in fetch_rss(url):
        if len(results) >= MAX_TICKER_ITEMS:
            break
        if MATERIAL_KEYWORDS.search(e["title"] + " " + e["summary"]):
            results.append({"title": e["title"].strip(), "summary": clean(e["summary"]), "link": e["link"], "published": e["published"]})
    return results


def fetch_quote(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        meta = r.json()["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice", 0)
        prev  = meta.get("chartPreviousClose", price)
        return {"price": round(price, 2), "change_pct": round((price - prev) / prev * 100 if prev else 0, 2)}
    except Exception as e:
        print(f"  [WARN] quote {symbol}: {e}")
        return {"price": 0, "change_pct": 0}


def main():
    with open("portfolio.json") as f:
        portfolio = json.load(f)["portfolio"]
    active = [p for p in portfolio if p["pct"] > 0]

    print("Indices...")
    indices = {
        "SP500":  fetch_quote("^GSPC"),
        "NASDAQ": fetch_quote("^IXIC"),
        "AEX":    fetch_quote("^AEX"),
    }
    for k, v in indices.items():
        print(f"  {k}: {v}")

    print("Marktnieuws...")
    market_news = get_market_news()
    print(f"  {len(market_news)} items")

    ticker_news = {}
    for pos in active:
        t = pos["ticker"]
        print(f"  {t}...")
        ticker_news[t] = get_ticker_news(t)

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "indices": indices,
        "market_news": market_news,
        "ticker_news": ticker_news,
        "portfolio": active,
    }
    with open("fetched_data.json", "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("fetched_data.json opgeslagen")


if __name__ == "__main__":
    main()
