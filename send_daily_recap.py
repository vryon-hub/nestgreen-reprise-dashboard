#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Envoie un email récapitulatif des reprises de la veille (heure de Paris),
par grade : nombre de téléphones et valeur totale en €.

Tourne une fois par jour (voir .github/workflows/daily-recap.yml), pas dans
le cycle de 15 min -> lit hourly_data.json déjà à jour (accumulé par
build_hourly_data.py à chaque cycle), ne refait aucun appel BackMarket.

Ne renvoie qu'une fois par jour de données (alert_state.json / last_recap_date),
au cas où le workflow se déclencherait deux fois le même jour.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from check_reprises_alert import send_email  # réutilise l'envoi SMTP déjà validé

PARIS = ZoneInfo("Europe/Paris")
HERE = Path(__file__).parent

HOURLY_DATA = HERE / "hourly_data.json"
VOLUME_DATA = HERE / "volume_data.json"
STATE_PATH = HERE / "alert_state.json"

MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin",
          "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def french_date(d):
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d.year}"


def build_email_html(by_grade, total_count, total_eur, d):
    date_str = french_date(d)
    rows_html = "".join(f"""
      <tr>
        <td style="padding:10px 0;border-bottom:1px solid #E5E5E0;font-size:14px;color:#242424;">{grade}</td>
        <td style="padding:10px 0;border-bottom:1px solid #E5E5E0;font-size:14px;color:#242424;text-align:right;font-variant-numeric:tabular-nums;">{count}</td>
        <td style="padding:10px 0;border-bottom:1px solid #E5E5E0;font-size:14px;color:#242424;text-align:right;font-variant-numeric:tabular-nums;">{eur:,.0f}&nbsp;&euro;</td>
      </tr>""".replace(",", " ") for grade, count, eur in by_grade)

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
        <p style="margin:0;font-size:13px;font-weight:600;color:#006A38;text-transform:uppercase;letter-spacing:0.05em;">Récapitulatif quotidien</p>
        <h1 style="margin:8px 0 0;font-size:24px;line-height:1.3;color:#242424;font-weight:700;">Reprises du {date_str}</h1>
      </td>
    </tr>
    <tr>
      <td style="padding:20px 28px 8px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td width="50%" style="background:#F0F4F1;border-radius:10px;padding:16px 18px;">
              <p style="margin:0;font-size:11.5px;font-weight:600;color:#8B948E;text-transform:uppercase;letter-spacing:0.05em;">Téléphones repris</p>
              <p style="margin:6px 0 0;font-size:28px;font-weight:700;color:#242424;">{total_count}</p>
            </td>
            <td width="12"></td>
            <td width="50%" style="background:#F0F4F1;border-radius:10px;padding:16px 18px;">
              <p style="margin:0;font-size:11.5px;font-weight:600;color:#8B948E;text-transform:uppercase;letter-spacing:0.05em;">Valeur totale</p>
              <p style="margin:6px 0 0;font-size:28px;font-weight:700;color:#242424;">{total_str}&nbsp;&euro;</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:12px 28px 28px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="padding:0 0 8px;font-size:11.5px;font-weight:600;color:#8B948E;text-transform:uppercase;letter-spacing:0.05em;">Grade</td>
            <td style="padding:0 0 8px;font-size:11.5px;font-weight:600;color:#8B948E;text-transform:uppercase;letter-spacing:0.05em;text-align:right;">Nb</td>
            <td style="padding:0 0 8px;font-size:11.5px;font-weight:600;color:#8B948E;text-transform:uppercase;letter-spacing:0.05em;text-align:right;">Valeur</td>
          </tr>{rows_html}
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:16px 28px;border-top:1px solid #E5E5E0;">
        <p style="margin:0;font-size:12px;color:#8B948E;">Récapitulatif automatique &middot; Grille Reprise Nestgreen</p>
      </td>
    </tr>
  </table>
</div>"""


def main():
    if not HOURLY_DATA.exists() or not VOLUME_DATA.exists():
        print("Données absentes, on saute.")
        return

    yesterday = (datetime.now(PARIS) - timedelta(days=1)).date()
    yesterday_str = yesterday.isoformat()

    hourly = json.loads(HOURLY_DATA.read_text(encoding="utf-8"))
    rows = hourly.get("days", {}).get(yesterday_str)
    if not rows:
        print(f"Pas de données pour {yesterday_str} dans hourly_data.json, on saute.")
        return

    grades = json.loads(VOLUME_DATA.read_text(encoding="utf-8"))["grades"]

    by_grade_idx = {}
    for _hour, _device_idx, grade_idx, count, price_sum, _price_count in rows:
        c, e = by_grade_idx.get(grade_idx, (0, 0.0))
        by_grade_idx[grade_idx] = (c + count, e + price_sum)

    by_grade = [(grades[gi], c, e) for gi, (c, e) in sorted(by_grade_idx.items()) if gi < len(grades)]
    total_count = sum(c for _, c, _ in by_grade)
    total_eur = sum(e for _, _, e in by_grade)

    if total_count == 0:
        print(f"0 reprise pour {yesterday_str}, pas d'envoi.")
        return

    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    if state.get("last_recap_date") == yesterday_str:
        print(f"Récapitulatif déjà envoyé pour {yesterday_str}.")
        return

    html = build_email_html(by_grade, total_count, total_eur, yesterday)
    send_email(f"Nestgreen - Récapitulatif des reprises du {yesterday.strftime('%d/%m/%Y')}", html)

    state["last_recap_date"] = yesterday_str
    STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
    print(f"Récapitulatif envoyé pour {yesterday_str} : {total_count} reprises, {total_eur:.0f} EUR.")


if __name__ == "__main__":
    main()
