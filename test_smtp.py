import smtplib, os
from email.mime.text import MIMEText

user = os.environ["GMAIL_USER"]
pwd  = os.environ["GMAIL_APP_PASSWORD"]

print(f"User: {user}")
print(f"Password length: {len(pwd)}")
print(f"Password (no spaces): {''.join(pwd.split())}")

msg = MIMEText("Test mail van beurs-briefing", "plain")
msg["Subject"] = "SMTP Test"
msg["From"] = user
msg["To"] = user

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
    s.login(user, ''.join(pwd.split()))
    s.sendmail(user, user, msg.as_string())
    print("SUCCESS — mail verstuurd!")
