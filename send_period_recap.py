#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Récapitulatifs HEBDOMADAIRE (lundi -> dimanche) et MENSUEL (mois calendaire)
des reprises, même mise en page que le récap quotidien (recap_email.py).

Appelé à chaque exécution nocturne de daily-recap.yml (22:30 et 23:30 UTC, pour
absorber le changement d'heure). À chaque appel on regarde la dernière période
TERMINÉE (heure de Paris) et on n'envoie que si elle n'a pas déjà été envoyée
(alert_state.json : last_weekly_start / last_monthly) -> le jour où une semaine
ou un mois se termine, ça part ; les autres jours, rien.

Premier passage (clés absentes de alert_state.json) : on mémorise simplement la
période en cours SANS envoyer, pour ne pas expédier d'un coup une période passée ;
le premier envoi réel est celui de la prochaine période terminée.

Source : volume_data.json (une ligne par jour/appareil/grade, tenue à jour à
chaque cycle). Les jours sans aucune donnée dans la période sont signalés dans
le mail (un total sous-estimé en silence serait pire qu'un avertissement).

Aperçu : --preview weekly|monthly|daily envoie la dernière période terminée à
v.ryon seul, préfixée [APERÇU], sans toucher à l'état.
"""
import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from check_reprises_alert import send_email, CC
from recap_email import MONTHS, build_recap_html

PARIS = ZoneInfo("Europe/Paris")
HERE = Path(__file__).parent
VOLUME_DATA = HERE / "volume_data.json"
STATE_PATH = HERE / "alert_state.json"

PERIOD_CC = f"{CC},g.toure@nest.green"  # mêmes destinataires que le récap quotidien
PREVIEW_TO = "v.ryon@nest.green"
MAX_DEVICE_ROWS = 30  # au-delà, regroupé en "Autres appareils" (131 appareils sur un mois)


def last_week(today):
    start = today - timedelta(days=today.weekday() + 7)  # lundi de la semaine précédente
    return start, start + timedelta(days=6)


def last_month(today):
    end = today.replace(day=1) - timedelta(days=1)
    return end.replace(day=1), end


def week_title(start, end):
    if start.year != end.year:
        return f"Semaine du {start.day} {MONTHS[start.month - 1]} {start.year} au {end.day} {MONTHS[end.month - 1]} {end.year}"
    if start.month != end.month:
        return f"Semaine du {start.day} {MONTHS[start.month - 1]} au {end.day} {MONTHS[end.month - 1]} {end.year}"
    return f"Semaine du {start.day} au {end.day} {MONTHS[end.month - 1]} {end.year}"


def aggregate(start, end):
    vol = json.loads(VOLUME_DATA.read_text(encoding="utf-8"))
    devices = vol["devices"]
    s, e = start.isoformat(), end.isoformat()
    per_device, days_seen = {}, set()
    for day, di, _gi, count, price_sum, _pc in vol["rows"]:
        if s <= day <= e:
            days_seen.add(day)
            c, v = per_device.get(di, (0, 0.0))
            per_device[di] = (c + count, v + price_sum)
    by_device = sorted(((devices[di], c, v) for di, (c, v) in per_device.items() if di < len(devices)),
                       key=lambda r: -r[1])
    expected = [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]
    missing = [d for d in expected if d not in days_seen]
    return by_device, sum(c for _, c, _ in by_device), sum(v for _, _, v in by_device), missing


def build_period(kind, start, end):
    by_device, total_count, total_eur, missing = aggregate(start, end)
    if kind == "weekly":
        eyebrow, title = "Récapitulatif hebdomadaire", week_title(start, end)
        subject = (f"Nestgreen - Récapitulatif hebdomadaire des reprises "
                   f"({start.strftime('%d/%m')} - {end.strftime('%d/%m/%Y')})")
    else:
        eyebrow, title = "Récapitulatif mensuel", f"Reprises de {MONTHS[start.month - 1]} {start.year}"
        subject = f"Nestgreen - Récapitulatif mensuel des reprises - {MONTHS[start.month - 1]} {start.year}"
    note = None
    if missing:
        shown = ", ".join(datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m") for d in missing[:6])
        note = (f"Attention : aucune donnée enregistrée pour {len(missing)} jour(s) de la période ({shown}"
                f"{'…' if len(missing) > 6 else ''}) — les totaux sont sous-estimés.")
    html = build_recap_html(eyebrow, title, by_device, total_count, total_eur,
                            max_rows=MAX_DEVICE_ROWS, note=note)
    return subject, html, total_count, total_eur, missing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", choices=["daily", "weekly", "monthly"],
                        help="envoie un aperçu à v.ryon uniquement, sans modifier l'état")
    args = parser.parse_args()

    if args.preview == "daily":
        import send_daily_recap
        send_daily_recap.main(preview=True)
        return
    if not VOLUME_DATA.exists():
        print("volume_data.json absent, on saute.")
        return

    today = datetime.now(PARIS).date()
    periods = {
        "weekly": ("last_weekly_start", *last_week(today), lambda s: s.isoformat()),
        "monthly": ("last_monthly", *last_month(today), lambda s: s.strftime("%Y-%m")),
    }

    if args.preview:
        key, start, end, _ = periods[args.preview]
        subject, html, count, eur, missing = build_period(args.preview, start, end)
        send_email(f"[APERÇU] {subject}", html, cc="", to=PREVIEW_TO)
        print(f"Aperçu {args.preview} ({start} -> {end}) envoyé à {PREVIEW_TO} uniquement : "
              f"{count} reprises, {eur:.0f} EUR, jours manquants : {missing or 'aucun'}.")
        return

    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    changed = False
    for kind, (key, start, end, marker) in periods.items():
        mark = marker(start)
        if key not in state:
            state[key] = mark
            changed = True
            print(f"{kind} : initialisation à {mark} (rien envoyé, premier envoi à la prochaine période terminée).")
            continue
        if state[key] == mark:
            print(f"{kind} : {mark} déjà traité.")
            continue
        subject, html, count, eur, missing = build_period(kind, start, end)
        if count == 0:
            print(f"{kind} : 0 reprise sur {start} -> {end}, pas d'envoi.")
            continue
        send_email(subject, html, cc=PERIOD_CC)
        state[key] = mark
        changed = True
        print(f"{kind} envoyé ({start} -> {end}) : {count} reprises, {eur:.0f} EUR, "
              f"jours manquants : {missing or 'aucun'}.")
        STATE_PATH.write_text(json.dumps(state), encoding="utf-8")  # écrit dès l'envoi (jamais deux fois)
    if changed:
        STATE_PATH.write_text(json.dumps(state), encoding="utf-8")


if __name__ == "__main__":
    main()
