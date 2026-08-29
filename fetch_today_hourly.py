#!/usr/bin/env python3
"""
Récupère les commandes buyback du jour même (heure de Paris, pas UTC — l'API
BackMarket renvoie des creationDate en UTC, donc sans conversion les heures
affichées dans le dashboard seraient décalées de 1-2h selon la saison), en
gardant l'heure de création (perdue dans orders_volume.json qui ne garde que
la date) pour permettre une vue "Jour" détaillée heure par heure.

Ne persiste AUCUNE donnée client — mêmes garanties que fetch_orders_volume.py.

Usage:
    export BM_API_KEY="<clé base64 user:token, avec padding ==>"
    python3 fetch_today_hourly.py
"""

import datetime
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

HOST = "www.backmarket.fr"
PAGE_SIZE = 100
DELAY = 0.6

RETRIABLE_NETWORK_ERRORS = (urllib.error.URLError, ConnectionError, TimeoutError, OSError)


def fetch(url, api_key):
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {api_key}",
            "Accept": "application/json",
            "User-Agent": "curl/8.7.1",
        },
    )
    for attempt in range(1, 6):
        try:
            with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                wait = 5 * attempt
                print(f"  HTTP {e.code}, retry dans {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"Erreur HTTP {e.code} sur {url}: {e.read()}", file=sys.stderr)
            return None
        except RETRIABLE_NETWORK_ERRORS as e:
            wait = 5 * attempt
            print(f"  Erreur réseau ({e}), retry dans {wait}s...", file=sys.stderr)
            time.sleep(wait)
            continue
    return None


def main():
    api_key = os.environ.get("BM_API_KEY")
    if not api_key:
        print("Erreur: variable d'environnement BM_API_KEY manquante.", file=sys.stderr)
        sys.exit(1)

    now_paris = datetime.datetime.now(PARIS)
    today = now_paris.strftime("%Y-%m-%d")
    # le filtre API est en UTC ; minuit local peut encore être "hier" en UTC (ex: 00h-02h
    # en été CEST) -> on interroge depuis minuit local converti en UTC pour ne rien manquer,
    # puis on filtre précisément côté client sur la date locale.
    midnight_utc = now_paris.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(datetime.timezone.utc)
    query_date = midnight_utc.strftime("%Y-%m-%d")
    url = f"https://{HOST}/ws/buyback/v1/orders?creationDate={query_date}&pageSize={PAGE_SIZE}"
    records = []
    page = 0
    total = None
    while url:
        page += 1
        data = fetch(url, api_key)
        if data is None:
            print("Échec, arrêt.", file=sys.stderr)
            break
        if total is None:
            total = data["count"]
            print(f"{total} commandes aujourd'hui ({today}).", file=sys.stderr)
        for o in data["results"]:
            created_local = datetime.datetime.fromisoformat(
                o["creationDate"].replace("Z", "+00:00")).astimezone(PARIS)
            # ne garder que les commandes créées AUJOURD'HUI en heure locale (le filtre
            # creationDate côté API est en UTC et sert juste de borne minimale large)
            if created_local.strftime("%Y-%m-%d") != today:
                continue
            price = o.get("counterOfferPrice") or o.get("originalPrice")
            records.append({
                "hour": created_local.hour,
                "status": o["status"],
                "device": o["listing"]["title"],
                "grade": o["listing"]["grade"],
                "price": price["value"] if price else None,
            })
        print(f"  page {page}: {len(records)}/{total}", file=sys.stderr)
        url = data.get("next")
        time.sleep(DELAY)

    with open("today_hourly.json", "w", encoding="utf-8") as f:
        json.dump({"date": today, "records": records}, f, ensure_ascii=False)
    print(f"Terminé: {len(records)} commandes écrites dans today_hourly.json.", file=sys.stderr)


if __name__ == "__main__":
    main()
