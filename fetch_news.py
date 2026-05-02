"""
fetch_news.py — haalt markt- en portfolionieuws op, schrijft fetched_data.json
en email_template.html. Geen Anthropic API calls; analyse gebeurt door Claude Code.
"""

import json
import os
import re
from datetime import datetime, timezone

import feedparser
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuratie
# ---------------------------------------------------------------------------

MARKET_FEEDS = [
    ("MarketWatch",  "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("Reuters",      "https://feeds.reuters.com/reuters/businessNews"),
    ("Google News",  "https://news.google.com/rss/search?q=stock+market&hl=en-US&gl=US&ceid=US:en"),
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

PORTFOLIO_FILE = "portfolio.json"
OUTPUT_FILE    = "fetched_data.json"
TEMPLATE_FILE  = "email_template.html"

MAX_MARKET_ITEMS    = 3
MAX_TICKER_ITEMS    = 3

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_feed(url: str, timeout: int = 10) -> list[dict]:
    try:
        d = feedparser.parse(url, request_headers={"User-Agent": "beurs-briefing/1.0"})
        return d.entries
    except Exception as e:
        print(f"  [WARN] feed error {url}: {e}")
        return []


def entry_text(entry) -> str:
    parts = [entry.get("title", ""), entry.get("summary", "")]
    return " ".join(parts)


def entry_link(entry) -> str:
    return entry.get("link", "")


def entry_published(entry) -> str:
    return entry.get("published", "")


def clean_summary(raw: str) -> str:
    soup = BeautifulSoup(raw or "", "html.parser")
    text = soup.get_text(" ", strip=True)
    return text[:280].strip()


def fetch_index_quote(symbol: str) -> dict:
    """Ophalen van index-quote via Yahoo Finance JSON endpoint."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
    headers = {"User-Agent": "beurs-briefing/1.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        meta = data["chart"]["result"][0]["meta"]
        price   = meta.get("regularMarketPrice", 0)
        prev    = meta.get("chartPreviousClose", price)
        chg_pct = ((price - prev) / prev * 100) if prev else 0
        return {"price": round(price, 2), "change_pct": round(chg_pct, 2)}
    except Exception as e:
        print(f"  [WARN] quote error {symbol}: {e}")
        return {"price": 0, "change_pct": 0}

# ---------------------------------------------------------------------------
# Marktnieuws
# ---------------------------------------------------------------------------

def get_market_news() -> list[dict]:
    results = []
    seen_titles: set[str] = set()

    for source, url in MARKET_FEEDS:
        if len(results) >= MAX_MARKET_ITEMS:
            break
        entries = fetch_feed(url)
        for e in entries:
            if len(results) >= MAX_MARKET_ITEMS:
                break
            title = e.get("title", "").strip()
            if title in seen_titles:
                continue
            if MARKET_KEYWORDS.search(entry_text(e)):
                seen_titles.add(title)
                results.append({
                    "title":     title,
                    "summary":   clean_summary(e.get("summary", "")),
                    "source":    source,
                    "link":      entry_link(e),
                    "published": entry_published(e),
                })

    return results

# ---------------------------------------------------------------------------
# Portfolio-nieuws per ticker
# ---------------------------------------------------------------------------

def yahoo_rss_url(ticker: str) -> str:
    return f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"


def get_ticker_news(ticker: str) -> list[dict]:
    entries = fetch_feed(yahoo_rss_url(ticker))
    results = []
    for e in entries:
        if len(results) >= MAX_TICKER_ITEMS:
            break
        text = entry_text(e)
        if MATERIAL_KEYWORDS.search(text):
            results.append({
                "title":     e.get("title", "").strip(),
                "summary":   clean_summary(e.get("summary", "")),
                "link":      entry_link(e),
                "published": entry_published(e),
            })
    return results

# ---------------------------------------------------------------------------
# Indices
# ---------------------------------------------------------------------------

INDEX_MAP = {
    "SP500":  "^GSPC",
    "NASDAQ": "^IXIC",
    "AEX":    "^AEX",
}


def get_indices() -> dict:
    return {name: fetch_index_quote(sym) for name, sym in INDEX_MAP.items()}

# ---------------------------------------------------------------------------
# Hoofd
# ---------------------------------------------------------------------------

def main():
    with open(PORTFOLIO_FILE) as f:
        portfolio = json.load(f)["portfolio"]

    active = [p for p in portfolio if p["pct"] > 0]

    print("Ophalen indices...")
    indices = get_indices()

    print("Ophalen marktnieuws...")
    market_news = get_market_news()
    print(f"  {len(market_news)} marktitems gevonden")

    ticker_news: dict[str, list] = {}
    for pos in active:
        ticker = pos["ticker"]
        print(f"  nieuws: {ticker}")
        ticker_news[ticker] = get_ticker_news(ticker)

    fetched = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "indices":       indices,
        "market_news":   market_news,
        "ticker_news":   ticker_news,
        "portfolio":     active,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(fetched, f, indent=2, ensure_ascii=False)
    print(f"Weggeschreven naar {OUTPUT_FILE}")

    write_template(active)
    print(f"Template weggeschreven naar {TEMPLATE_FILE}")


# ---------------------------------------------------------------------------
# HTML email template
# ---------------------------------------------------------------------------

def pct_color_class(val: float) -> str:
    return "positive" if val >= 0 else "negative"


def write_template(active_positions: list[dict]):
    tickers_with_news = [p for p in active_positions]

    portfolio_rows = ""
    for pos in tickers_with_news:
        t = pos["ticker"]
        portfolio_rows += f"""
        <tr class="portfolio-row">
          <td><span class="ticker-badge">{t}</span></td>
          <td>{pos['name']}</td>
          <td class="pct-col">{pos['pct']}%</td>
          <td><span class="label label-{{LABEL_{t}}}">{{LABEL_{t}}}</span></td>
          <td>{{WAT_{t}}}</td>
          <td>{{ADVIES_{t}}}</td>
          <td><a href="{{LINK_{t}}}" class="news-link">bericht</a></td>
        </tr>"""

    market_news_rows = ""
    for i in range(1, MAX_MARKET_ITEMS + 1):
        market_news_rows += f"""
        <div class="news-item">
          <div class="news-title">{{MARKET_TITLE_{i}}}</div>
          <div class="news-summary">{{MARKET_SUMMARY_{i}}}</div>
          <div class="news-meta">{{MARKET_SOURCE_{i}}} &mdash; <a href="{{MARKET_LINK_{i}}}">lees meer</a></div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dagelijkse beursupdate</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f0f2f5; color: #1a1a2e; }}
    a {{ color: #0C447C; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    /* Header */
    .header {{ background: #0C447C; padding: 28px 40px; color: #fff; }}
    .header h1 {{ font-size: 22px; font-weight: 700; letter-spacing: 0.3px; }}
    .header .date {{ margin-top: 4px; font-size: 13px; opacity: 0.75; }}

    /* Container */
    .container {{ max-width: 760px; margin: 0 auto; padding: 24px 16px; }}

    /* Metric cards */
    .metrics {{ display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }}
    .metric-card {{ flex: 1; min-width: 180px; background: #fff;
                    border-radius: 10px; padding: 18px 20px;
                    box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
    .metric-card .label {{ font-size: 11px; font-weight: 600; text-transform: uppercase;
                            letter-spacing: 0.8px; color: #6b7280; margin-bottom: 6px; }}
    .metric-card .value {{ font-size: 26px; font-weight: 700; color: #1a1a2e; }}
    .metric-card .change {{ font-size: 13px; font-weight: 600; margin-top: 4px; }}
    .positive {{ color: #16a34a; }}
    .negative {{ color: #dc2626; }}

    /* Section */
    .section {{ background: #fff; border-radius: 10px; padding: 24px 28px;
                margin-bottom: 24px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
    .section-title {{ font-size: 15px; font-weight: 700; color: #0C447C;
                      text-transform: uppercase; letter-spacing: 0.6px;
                      border-bottom: 2px solid #e5e7eb; padding-bottom: 10px;
                      margin-bottom: 18px; }}

    /* Marktnieuws */
    .news-item {{ padding: 14px 0; border-bottom: 1px solid #f3f4f6; }}
    .news-item:last-child {{ border-bottom: none; padding-bottom: 0; }}
    .news-title {{ font-size: 14px; font-weight: 600; margin-bottom: 4px; }}
    .news-summary {{ font-size: 13px; color: #4b5563; line-height: 1.5; margin-bottom: 5px; }}
    .news-meta {{ font-size: 11px; color: #9ca3af; }}
    .news-link {{ font-size: 12px; }}

    /* Portfolio tabel */
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ text-align: left; font-size: 11px; font-weight: 600; text-transform: uppercase;
          letter-spacing: 0.6px; color: #6b7280; padding: 6px 10px 10px; }}
    td {{ padding: 10px; border-top: 1px solid #f3f4f6; vertical-align: top; }}
    .portfolio-row:hover td {{ background: #fafafa; }}

    .ticker-badge {{ display: inline-block; background: #0C447C; color: #fff;
                     font-size: 11px; font-weight: 700; padding: 2px 7px;
                     border-radius: 4px; letter-spacing: 0.5px; }}
    .pct-col {{ font-weight: 600; color: #374151; white-space: nowrap; }}

    .label {{ display: inline-block; font-size: 10px; font-weight: 700;
              padding: 2px 8px; border-radius: 12px; letter-spacing: 0.5px; }}
    .label-BULLISH  {{ background: #dcfce7; color: #15803d; }}
    .label-BEARISH  {{ background: #fee2e2; color: #b91c1c; }}
    .label-NEUTRAAL {{ background: #f3f4f6; color: #6b7280; }}

    /* Actiepunten */
    .action-list {{ list-style: none; counter-reset: action-counter; }}
    .action-list li {{ counter-increment: action-counter; display: flex;
                       align-items: flex-start; gap: 12px; padding: 10px 0;
                       border-bottom: 1px solid #f3f4f6; font-size: 14px; }}
    .action-list li:last-child {{ border-bottom: none; }}
    .action-list li::before {{ content: counter(action-counter);
                               display: flex; align-items: center; justify-content: center;
                               min-width: 24px; height: 24px; background: #0C447C;
                               color: #fff; font-size: 12px; font-weight: 700;
                               border-radius: 50%; flex-shrink: 0; margin-top: 1px; }}

    /* Footer */
    .footer {{ text-align: center; font-size: 12px; color: #9ca3af; padding: 16px 0 32px; }}
  </style>
</head>
<body>

  <div class="header">
    <h1>Dagelijkse beursupdate</h1>
    <div class="date">{{DATE_LONG}}</div>
  </div>

  <div class="container">

    <!-- Metric cards -->
    <div class="metrics">
      <div class="metric-card">
        <div class="label">S&amp;P 500</div>
        <div class="value">{{SP500_VALUE}}</div>
        <div class="change {{SP500_COLOR_CLASS}}">{{SP500_CHANGE}}</div>
      </div>
      <div class="metric-card">
        <div class="label">Nasdaq</div>
        <div class="value">{{NASDAQ_VALUE}}</div>
        <div class="change {{NASDAQ_COLOR_CLASS}}">{{NASDAQ_CHANGE}}</div>
      </div>
      <div class="metric-card">
        <div class="label">AEX</div>
        <div class="value">{{AEX_VALUE}}</div>
        <div class="change {{AEX_COLOR_CLASS}}">{{AEX_CHANGE}}</div>
      </div>
    </div>

    <!-- Marktoverzicht -->
    <div class="section">
      <div class="section-title">Marktoverzicht</div>
      {market_news_rows}
    </div>

    <!-- Portfolio materieel nieuws -->
    <div class="section">
      <div class="section-title">Portfolio &mdash; materieel nieuws</div>
      <table>
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Naam</th>
            <th>%</th>
            <th>Sentiment</th>
            <th>Wat</th>
            <th>Advies</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {portfolio_rows}
        </tbody>
      </table>
    </div>

    <!-- Vandaag in de gaten houden -->
    <div class="section">
      <div class="section-title">Vandaag in de gaten houden</div>
      <ol class="action-list">
        <li>{{ACTIE_1}}</li>
        <li>{{ACTIE_2}}</li>
        <li>{{ACTIE_3}}</li>
      </ol>
    </div>

    <div class="footer">
      Volgende update: {{NEXT_UPDATE_TIME}} &bull; {{GMAIL_USER}}
    </div>

  </div>
</body>
</html>
"""
    with open(TEMPLATE_FILE, "w") as f:
        f.write(html)


if __name__ == "__main__":
    main()
