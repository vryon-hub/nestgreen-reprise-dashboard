#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Envoie un email récapitulatif des reprises de la veille (heure de Paris),
par appareil : nombre de téléphones et valeur totale en €.

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

from check_reprises_alert import send_email, CC  # réutilise l'envoi SMTP déjà validé
from recap_email import build_recap_html, french_date

DAILY_RECAP_CC = f"{CC},g.toure@nest.green"
PREVIEW_TO = "v.ryon@nest.green"  # aperçus : jamais envoyés aux destinataires habituels

PARIS = ZoneInfo("Europe/Paris")
HERE = Path(__file__).parent

HOURLY_DATA = HERE / "hourly_data.json"
VOLUME_DATA = HERE / "volume_data.json"
STATE_PATH = HERE / "alert_state.json"


def main(preview=False):
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

    devices = json.loads(VOLUME_DATA.read_text(encoding="utf-8"))["devices"]

    by_device_idx = {}
    for _hour, device_idx, _grade_idx, count, price_sum, _price_count in rows:
        c, e = by_device_idx.get(device_idx, (0, 0.0))
        by_device_idx[device_idx] = (c + count, e + price_sum)

    # trié par nombre de reprises décroissant (les appareils les plus repris en premier)
    by_device = sorted(
        ((devices[di], c, e) for di, (c, e) in by_device_idx.items() if di < len(devices)),
        key=lambda row: -row[1],
    )
    total_count = sum(c for _, c, _ in by_device)
    total_eur = sum(e for _, _, e in by_device)

    if total_count == 0:
        print(f"0 reprise pour {yesterday_str}, pas d'envoi.")
        return

    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    if not preview and state.get("last_recap_date") == yesterday_str:
        print(f"Récapitulatif déjà envoyé pour {yesterday_str}.")
        return

    html = build_recap_html("Récapitulatif quotidien", f"Reprises du {french_date(yesterday)}",
                            by_device, total_count, total_eur)
    subject = f"Nestgreen - Récapitulatif des reprises du {yesterday.strftime('%d/%m/%Y')}"
    if preview:
        send_email(f"[APERÇU] {subject}", html, cc="", to=PREVIEW_TO)
        print(f"Aperçu quotidien ({yesterday_str}) envoyé à {PREVIEW_TO} uniquement : {total_count} reprises.")
        return
    send_email(subject, html, cc=DAILY_RECAP_CC)

    state["last_recap_date"] = yesterday_str
    STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
    print(f"Récapitulatif envoyé pour {yesterday_str} : {total_count} reprises, {total_eur:.0f} EUR.")


if __name__ == "__main__":
    main()
