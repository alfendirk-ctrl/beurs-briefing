"""
analyze_and_generate.py — roept Claude API aan om fetched_data.json te analyseren
en alle placeholders in email_template.html in te vullen → email_final.html
"""

import json
import os
from datetime import datetime, timedelta

import anthropic

DATA_FILE     = "fetched_data.json"
TEMPLATE_FILE = "email_template.html"
OUTPUT_FILE   = "email_final.html"


def dutch_date(dt: datetime) -> str:
    days   = ["maandag","dinsdag","woensdag","donderdag","vrijdag","zaterdag","zondag"]
    months = ["januari","februari","maart","april","mei","juni",
              "juli","augustus","september","oktober","november","december"]
    return f"{days[dt.weekday()]} {dt.day} {months[dt.month - 1]} {dt.year}"


def next_update_str(dt: datetime) -> str:
    days   = ["maandag","dinsdag","woensdag","donderdag","vrijdag","zaterdag","zondag"]
    months = ["januari","februari","maart","april","mei","juni",
              "juli","augustus","september","oktober","november","december"]
    nd = dt + timedelta(days=1)
    while nd.weekday() >= 5:
        nd += timedelta(days=1)
    return f"{days[nd.weekday()]} {nd.day} {months[nd.month - 1]} om 08:00"


def main():
    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)

    with open(TEMPLATE_FILE, encoding="utf-8") as f:
        template = f.read()

    now = datetime.now()
    data["meta"] = {
        "date_long":   dutch_date(now),
        "next_update": next_update_str(now),
        "gmail_user":  "alfendirk@gmail.com",
    }

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    system_prompt = """Je bent een financieel analist die dagelijkse beursberichten schrijft in het Nederlands.
Je taak: vul een HTML email template in op basis van opgehaalde marktdata en nieuwsberichten.

Regels:
- Geef ALLEEN de ingevulde HTML terug, geen uitleg, geen markdown code blocks
- Vervang ALLE {PLACEHOLDER} variabelen — er mogen geen accolades meer zichtbaar zijn
- Sentiment labels: exact BULLISH, BEARISH of NEUTRAAL (hoofdletters)
- Color classes: exact "positive" (groen) of "negative" (rood) op basis van koersrichting
- {WAT_X}: één korte zin — wat is er concreet gebeurd? (Nederlands)
- {ADVIES_X}: één korte zin — wat betekent dit voor de positie? (Nederlands)
- Geen nieuws voor een ticker → NEUTRAAL, WAT = "Geen materieel nieuws vandaag.", ADVIES = "Houd positie aan."
- Indexwaarden: schrijf als getal met punt als duizendtalscheiding (bijv. 5.421,30)
- Als indexdata ontbreekt (waarde 0) → schrijf "–" als waarde en laat wijziging leeg
- {GMAIL_USER} → alfendirk@gmail.com"""

    data_str = json.dumps(data, indent=2, ensure_ascii=False)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"HTML template:\n\n{template}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": f"Opgehaalde data voor vandaag:\n\n{data_str}\n\nVul de template volledig in en geef alleen de HTML terug.",
                    },
                ],
            }
        ],
    )

    html = message.content[0].text.strip()

    # Strip markdown code blocks indien aanwezig
    if html.startswith("```"):
        html = html.split("\n", 1)[1]
        html = html.rsplit("```", 1)[0].strip()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    usage = message.usage
    print(f"email_final.html gegenereerd ({len(html)} tekens)")
    print(f"Tokens: input={usage.input_tokens}, output={usage.output_tokens}, cache_read={getattr(usage, 'cache_read_input_tokens', 0)}")


if __name__ == "__main__":
    main()
