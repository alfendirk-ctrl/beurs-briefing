"""
send_email.py — verstuurt email_final.html via Gmail SMTP SSL.
Wordt aangeroepen nadat Claude Code de placeholders heeft ingevuld.
"""

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

GMAIL_USER     = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
TO_ADDRESS     = "alfendirk@gmail.com"
HTML_FILE      = "email_final.html"


def main():
    with open(HTML_FILE, encoding="utf-8") as f:
        html_body = f.read()

    today = datetime.now().strftime("%-d %B %Y")
    subject = f"Beursupdate {today}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = TO_ADDRESS
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, TO_ADDRESS, msg.as_string())

    print(f"Email verstuurd naar {TO_ADDRESS} — onderwerp: {subject}")


if __name__ == "__main__":
    main()
