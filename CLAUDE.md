# Beurs Briefing

De volledige pipeline draait automatisch in GitHub Actions:

```
fetch_news.py → fetched_data.json + email_template.html
                              ↓
             analyze_and_generate.py (Claude API)
                              ↓
                       email_final.html
                              ↓
                    send_email.py → inbox
```

Trigger: dagelijks om 09:00 CEST op werkdagen (of handmatig via workflow_dispatch).

## Benodigde GitHub Actions secrets

| Secret | Doel |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API voor analyse |
| `GMAIL_USER` | Gmail verzendadres |
| `GMAIL_APP_PASSWORD` | Gmail App Password |
| `GH_PAT` | Optioneel: handmatig committen via commit_email_final() |

## Handmatig triggeren

github.com/alfendirk-ctrl/beurs-briefing/actions → Dagelijkse beursupdate → Run workflow
