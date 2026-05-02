# Beurs Briefing

Dagelijkse beursupdate via email — gegenereerd door Claude Code.

## Wat doet het

1. **`fetch_news.py`** haalt data op en schrijft twee bestanden:
   - `fetched_data.json` — ruwe data: indices (S&P 500, Nasdaq, AEX), marktnieuws (RSS), en per ticker materieel portfolionieuws (Yahoo Finance RSS)
   - `email_template.html` — HTML email met placeholders (`{SP500_VALUE}`, `{WAT_NVDA}`, etc.)

2. **Claude Code** leest `fetched_data.json`, analyseert elk nieuwsitem, vult de placeholders in en verstuurt de email via Gmail SMTP.

## Hoe de routine werkt

```
fetch_news.py → fetched_data.json
                              ↓
                        Claude Code
                              ↓
                   email_template.html (ingevuld)
                              ↓
                         Gmail SMTP → inbox
```

`fetch_news.py` doet **geen** AI-aanroepen. Filtering is op trefwoorden gebaseerd.  
Posities met `pct: 0.0` worden overgeslagen.

## Installatie

```bash
pip install -r requirements.txt
```

## Secrets

Stel de volgende omgevingsvariabelen in (bijv. via `.env` of GitHub Actions secrets):

| Variabele          | Omschrijving                              |
|--------------------|-------------------------------------------|
| `GMAIL_USER`       | Gmail-adres dat de email verstuurt        |
| `GMAIL_APP_PASSWORD` | Gmail App Password (2FA vereist)        |

## Gebruik

```bash
python fetch_news.py
```

Daarna voert Claude Code de analyse uit en vult `email_template.html` in.
