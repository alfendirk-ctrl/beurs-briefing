"""
fetch_news.py — haalt markt- en portfolionieuws op via RSS (stdlib XML),
schrijft fetched_data.json en email_template.html.
Gebruikt geen feedparser — alleen stdlib + requests + beautifulsoup4.
"""

import base64
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

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

MAX_MARKET_ITEMS = 3
MAX_TICKER_ITEMS = 3

GITHUB_OWNER = "alfendirk-ctrl"
GITHUB_REPO  = "beurs-briefing"

HEADERS = {"User-Agent": "beurs-briefing/1.0"}

# ---------------------------------------------------------------------------
# RSS via stdlib XML
# ---------------------------------------------------------------------------

def fetch_rss(url: str) -> list[dict]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = []
        for item in root.iter("item"):
            def tag(name):
                el = item.find(name)
                return (el.text or "").strip() if el is not None else ""
            items.append({
                "title":     tag("title"),
                "summary":   tag("description"),
                "link":      tag("link"),
                "published": tag("pubDate"),
            })
        return items
    except Exception as e:
        print(f"  [WARN] {url}: {e}")
        return []


def clean_summary(raw: str) -> str:
    text = BeautifulSoup(raw or "", "html.parser").get_text(" ", strip=True)
    return text[:280].strip()

# ---------------------------------------------------------------------------
# Marktnieuws
# ---------------------------------------------------------------------------

def get_market_news() -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()
    for source, url in MARKET_FEEDS:
        if len(results) >= MAX_MARKET_ITEMS:
            break
        for e in fetch_rss(url):
            if len(results) >= MAX_MARKET_ITEMS:
                break
            title = e["title"]
            if title in seen:
                continue
            if MARKET_KEYWORDS.search(title + " " + e["summary"]):
                seen.add(title)
                results.append({
                    "title":     title,
                    "summary":   clean_summary(e["summary"]),
                    "source":    source,
                    "link":      e["link"],
                    "published": e["published"],
                })
    return results

# ---------------------------------------------------------------------------
# Portfolio-nieuws per ticker
# ---------------------------------------------------------------------------

def get_ticker_news(ticker: str) -> list[dict]:
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    results = []
    for e in fetch_rss(url):
        if len(results) >= MAX_TICKER_ITEMS:
            break
        if MATERIAL_KEYWORDS.search(e["title"] + " " + e["summary"]):
            results.append({
                "title":     e["title"],
                "summary":   clean_summary(e["summary"]),
                "link":      e["link"],
                "published": e["published"],
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


def fetch_index_quote(symbol: str) -> dict:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        meta = r.json()["chart"]["result"][0]["meta"]
        price   = meta.get("regularMarketPrice", 0)
        prev    = meta.get("chartPreviousClose", price)
        chg_pct = round((price - prev) / prev * 100, 2) if prev else 0
        return {"price": round(price, 2), "change_pct": chg_pct}
    except Exception as e:
        print(f"  [WARN] quote {symbol}: {e}")
        return {"price": 0, "change_pct": 0}


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

def write_template(active_positions: list[dict]):
    portfolio_rows = ""
    for pos in active_positions:
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
    .header {{ background: #0C447C; padding: 28px 40px; color: #fff; }}
    .header h1 {{ font-size: 22px; font-weight: 700; letter-spacing: 0.3px; }}
    .header .date {{ margin-top: 4px; font-size: 13px; opacity: 0.75; }}
    .container {{ max-width: 760px; margin: 0 auto; padding: 24px 16px; }}
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
    .section {{ background: #fff; border-radius: 10px; padding: 24px 28px;
                margin-bottom: 24px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
    .section-title {{ font-size: 15px; font-weight: 700; color: #0C447C;
                      text-transform: uppercase; letter-spacing: 0.6px;
                      border-bottom: 2px solid #e5e7eb; padding-bottom: 10px;
                      margin-bottom: 18px; }}
    .news-item {{ padding: 14px 0; border-bottom: 1px solid #f3f4f6; }}
    .news-item:last-child {{ border-bottom: none; padding-bottom: 0; }}
    .news-title {{ font-size: 14px; font-weight: 600; margin-bottom: 4px; }}
    .news-summary {{ font-size: 13px; color: #4b5563; line-height: 1.5; margin-bottom: 5px; }}
    .news-meta {{ font-size: 11px; color: #9ca3af; }}
    .news-link {{ font-size: 12px; }}
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
    .footer {{ text-align: center; font-size: 12px; color: #9ca3af; padding: 16px 0 32px; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>Dagelijkse beursupdate</h1>
    <div class="date">{{DATE_LONG}}</div>
  </div>
  <div class="container">
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
    <div class="section">
      <div class="section-title">Marktoverzicht</div>
      {market_news_rows}
    </div>
    <div class="section">
      <div class="section-title">Portfolio &mdash; materieel nieuws</div>
      <table>
        <thead>
          <tr>
            <th>Ticker</th><th>Naam</th><th>%</th>
            <th>Sentiment</th><th>Wat</th><th>Advies</th><th></th>
          </tr>
        </thead>
        <tbody>{portfolio_rows}</tbody>
      </table>
    </div>
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


# ---------------------------------------------------------------------------
# GitHub: commit email_final.html en trigger workflow (optioneel / handmatig)
# ---------------------------------------------------------------------------

def commit_email_final(token: str | None = None) -> None:
    token = token or os.environ.get("GH_PAT")
    if not token:
        raise RuntimeError("Stel GH_PAT in als omgevingsvariabele.")

    hdrs = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    api_base = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"

    with open("email_final.html", "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()

    url = f"{api_base}/contents/email_final.html"
    r = requests.get(url, headers=hdrs)
    sha = r.json().get("sha") if r.status_code == 200 else None

    payload: dict = {
        "message": f"Update email_final.html — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "content": content_b64,
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha

    requests.put(url, headers=hdrs, json=payload).raise_for_status()
    print("email_final.html gecommit naar main")

    requests.post(
        f"{api_base}/actions/workflows/send_email.yml/dispatches",
        headers=hdrs,
        json={"ref": "main"},
    ).raise_for_status()
    print("Workflow send_email.yml getriggerd")


if __name__ == "__main__":
    main()
