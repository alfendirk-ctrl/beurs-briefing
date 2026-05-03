# Beurs Briefing — Claude Code routineinstructies

Deze routine wordt dagelijks uitgevoerd door Claude Code.

## Stappen

### Stap 1 — Haal nieuws op
Voer `fetch_news.py` uit:
```bash
python fetch_news.py
```
Dit genereert:
- `fetched_data.json` — ruwe data (indices, marktnieuws, ticker-nieuws)
- `email_template.html` — HTML-template met placeholders

### Stap 2 — Analyseer het nieuws
Lees `fetched_data.json`. Beoordeel per ticker:
- **Sentiment**: BULLISH / BEARISH / NEUTRAAL
- **Wat**: één zin — wat is er concreet gebeurd?
- **Advies**: één zin — wat betekent dit voor de positie?
- **Label**: BULLISH / BEARISH / NEUTRAAL
- **Link**: URL van het meest relevante nieuwsitem

Schrijf ook:
- 3 marktitems (MARKET_TITLE/SUMMARY/SOURCE/LINK 1–3)
- 3 actiepunten (ACTIE_1, ACTIE_2, ACTIE_3)
- Indexwaarden: SP500_VALUE/CHANGE/COLOR_CLASS, idem voor NASDAQ en AEX
- DATE_LONG (bijv. "zaterdag 3 mei 2025")
- NEXT_UPDATE_TIME (volgende werkdag 08:00)
- GMAIL_USER (alfendirk@gmail.com)

### Stap 3 — Vul de template in
Lees `email_template.html`. Vervang alle `{PLACEHOLDER}` met de geanalyseerde waarden.
Sla het resultaat op als `email_final.html`.

### Stap 4 — Valideer
Controleer of alle placeholders vervangen zijn. Geen `{...}` mag nog zichtbaar zijn.

### Stap 5 — Commit en trigger
Commit `email_final.html` naar de main branch en trigger de GitHub Actions workflow:
```python
from fetch_news import commit_email_final
commit_email_final()  # gebruikt env var GITHUB_TOKEN
```
`GITHUB_TOKEN` moet een Fine-grained PAT zijn met rechten:
- **Contents: write** (voor commit)
- **Actions: write** (voor workflow dispatch)

De workflow `send_email.yml` verstuurt daarna automatisch de email.
