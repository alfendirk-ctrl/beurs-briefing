"""
run_fetch.py — voert fetch_news.main() uit maar vervangt feedparser
met een lichte XML-gebaseerde RSS-parser.
"""
import sys
import types
import xml.etree.ElementTree as ET
import requests

# ---------------------------------------------------------------------------
# Minimale feedparser-compatibele stub
# ---------------------------------------------------------------------------

class _Entry(dict):
    def get(self, key, default=None):
        return super().get(key, default)


def _parse_rss(url: str, headers: dict | None = None) -> list[_Entry]:
    headers = headers or {"User-Agent": "beurs-briefing/1.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as e:
        print(f"  [WARN] feed error {url}: {e}")
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = []

    # RSS 2.0 / RSS 1.0
    for item in root.iter("item"):
        e = _Entry()
        e["title"]     = (item.findtext("title")   or "").strip()
        e["summary"]   = (item.findtext("description") or "").strip()
        e["link"]      = (item.findtext("link")    or "").strip()
        e["published"] = (item.findtext("pubDate") or "").strip()
        entries.append(e)

    # Atom feeds
    if not entries:
        for item in root.iter("{http://www.w3.org/2005/Atom}entry"):
            e = _Entry()
            e["title"]   = (item.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
            summary_el   = item.find("{http://www.w3.org/2005/Atom}summary")
            content_el   = item.find("{http://www.w3.org/2005/Atom}content")
            e["summary"] = ((summary_el.text if summary_el is not None else None)
                            or (content_el.text if content_el is not None else None) or "").strip()
            link_el      = item.find("{http://www.w3.org/2005/Atom}link")
            e["link"]    = (link_el.get("href", "") if link_el is not None else "").strip()
            pub_el       = item.find("{http://www.w3.org/2005/Atom}published") or \
                           item.find("{http://www.w3.org/2005/Atom}updated")
            e["published"] = (pub_el.text if pub_el is not None else "").strip()
            entries.append(e)

    return entries


class _FakeFeedResult:
    def __init__(self, entries):
        self.entries = entries


def _fake_parse(url, request_headers=None, **kwargs):
    return _FakeFeedResult(_parse_rss(url, request_headers))


# Zet de nep-module klaar VOOR de import van fetch_news
fake_fp = types.ModuleType("feedparser")
fake_fp.parse = _fake_parse
sys.modules["feedparser"] = fake_fp

# ---------------------------------------------------------------------------
# Nu fetch_news importeren en uitvoeren
# ---------------------------------------------------------------------------
import fetch_news  # noqa: E402  (import na sys.modules patch is opzettelijk)
fetch_news.main()
