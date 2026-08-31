#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Envoie une alerte email quand le nombre de reprises initiées AUJOURD'HUI
(heure de Paris) atteint THRESHOLD. Tourne à chaque cycle (voir refresh.yml),
juste après fetch_today_hourly.py.

Ne renvoie qu'une fois par jour (alert_state.json garde la dernière date
alertée) — sinon un email à chaque cycle de 15 min une fois le seuil dépassé.
"""
import json
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from zoneinfo import ZoneInfo

from competitor_snapshot import freeze_snapshot

PARIS = ZoneInfo("Europe/Paris")
HERE = Path(__file__).parent

THRESHOLD = 500
RECIPIENT = "a.kurzynski@pixmania.com"
CC = "v.ryon@nest.green"
TODAY_HOURLY = HERE / "today_hourly.json"
STATE_PATH = HERE / "alert_state.json"

MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin",
          "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def french_date(d):
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d.year}"


def build_email_html(count, total_eur, d):
    date_str = french_date(d)
    total_str = f"{total_eur:,.0f}".replace(",", " ")
    return f"""<div style="background:#FAFAFA;padding:32px 16px;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#FFFFFF;border-radius:12px;overflow:hidden;border:1px solid #E5E5E0;">
    <tr>
      <td style="background:#006A38;padding:20px 28px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="font-size:15px;font-weight:700;color:#FFFFFF;letter-spacing:0.02em;">Nestgreen</td>
            <td style="text-align:right;font-size:13px;color:#E5F0E9;">Grille Reprise</td>
          </tr>
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:32px 28px 8px;">
        <p style="margin:0;font-size:13px;font-weight:600;color:#006A38;text-transform:uppercase;letter-spacing:0.05em;">Seuil atteint</p>
        <h1 style="margin:8px 0 0;font-size:24px;line-height:1.3;color:#242424;font-weight:700;">{THRESHOLD} reprises initiées aujourd'hui</h1>
        <p style="margin:8px 0 0;font-size:14px;color:#5B6560;">{date_str} &middot; heure de Paris</p>
      </td>
    </tr>
    <tr>
      <td style="padding:20px 28px 8px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td width="50%" style="background:#F0F4F1;border-radius:10px;padding:16px 18px;">
              <p style="margin:0;font-size:11.5px;font-weight:600;color:#8B948E;text-transform:uppercase;letter-spacing:0.05em;">Téléphones repris</p>
              <p style="margin:6px 0 0;font-size:28px;font-weight:700;color:#242424;">{count}</p>
            </td>
            <td width="12"></td>
            <td width="50%" style="background:#F0F4F1;border-radius:10px;padding:16px 18px;">
              <p style="margin:0;font-size:11.5px;font-weight:600;color:#8B948E;text-transform:uppercase;letter-spacing:0.05em;">Total achat</p>
              <p style="margin:6px 0 0;font-size:28px;font-weight:700;color:#242424;">{total_str}&nbsp;&euro;</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:20px 28px 28px;">
        <p style="margin:0;font-size:13.5px;line-height:1.6;color:#5B6560;">
          Ce seuil est surveillé car un volume élevé de reprises sur une même journée a déjà coïncidé avec une mise hors ligne temporaire des annonces BackMarket. Une vérification côté back-office est recommandée.
        </p>
      </td>
    </tr>
    <tr>
      <td style="padding:16px 28px;border-top:1px solid #E5E5E0;">
        <p style="margin:0;font-size:12px;color:#8B948E;">Alerte automatique &middot; Grille Reprise Nestgreen</p>
      </td>
    </tr>
  </table>
</div>"""


def send_email(subject, html, cc=CC):
    user = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = RECIPIENT
    msg["Cc"] = cc
    msg.attach(MIMEText(html, "html", "utf-8"))
    cc_list = [addr.strip() for addr in cc.split(",")]
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(user, [RECIPIENT, *cc_list], msg.as_string())


def main():
    if not TODAY_HOURLY.exists():
        print("today_hourly.json absent, on saute.")
        return

    data = json.loads(TODAY_HOURLY.read_text(encoding="utf-8"))
    now_paris = datetime.now(PARIS)
    today = now_paris.strftime("%Y-%m-%d")

    if data.get("date") != today:
        print(f"today_hourly.json daté {data.get('date')}, pas {today} -> pas encore rafraîchi pour aujourd'hui, on saute.")
        return

    records = data["records"]
    count = len(records)
    total_eur = sum(r["price"] for r in records if r.get("price") is not None)

    if count < THRESHOLD:
        print(f"{count}/{THRESHOLD} reprises aujourd'hui, pas d'alerte.")
        return

    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    if state.get("last_alert_date") == today:
        print(f"Alerte déjà envoyée aujourd'hui ({today}), {count} reprises actuellement.")
        return

    # fige les prix concurrents (repère/ptw) au moment précis où le seuil est atteint
    snapshot_path = freeze_snapshot("seuil_500_reprises")
    print(f"Prix concurrents figés dans {snapshot_path}" if snapshot_path else "Pas d'état sain antérieur à figer.")

    html = build_email_html(count, total_eur, now_paris.date())
    send_email(f"Nestgreen - {THRESHOLD} reprises atteintes aujourd'hui", html)

    state["last_alert_date"] = today
    STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
    print(f"Alerte envoyée à {RECIPIENT} : {count} reprises, {total_eur:.0f} EUR.")


if __name__ == "__main__":
    main()
