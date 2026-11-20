#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reconstruit, en UN passage sur l'API BackMarket, les lignes jour (volume_data.json)
et heure par heure (hourly_data.json) AVEC le pays d'achat, à partir d'une date.

Pourquoi : le pays (market) existe sur chaque commande mais n'était pas conservé dans les
agrégats ; et l'API ne propose qu'une date de création MINIMALE (pas de borne haute), donc
un passage par jour serait quadratique -> un seul passage depuis la date la plus ancienne,
puis découpage par date locale (Paris).

Remplace, pour les jours >= since :
  - les lignes de volume_data.json (jour x appareil x grade x pays) ;
  - le détail horaire de hourly_data.json, conservé depuis HOURLY_FROM (comme avant).
Les jours antérieurs ne sont pas touchés. Si une page de l'API échoue, RIEN n'est écrit.

Usage :
    export BM_API_KEY="..."
    python3 rebuild_orders_by_market.py 2026-06-07
"""
import datetime
import os
import sys
import time
from collections import defaultdict

from fetch_today_hourly import DELAY, HOST, PAGE_SIZE, PARIS, fetch
from grade_mapping import ORDER_GRADE_TO_LABEL
from volume_common import ensure_index, load_json, save_json

HOURLY_FROM = "2026-08-28"  # le détail horaire n'a jamais été conservé avant cette date


def main():
    api_key = os.environ.get("BM_API_KEY")
    if not api_key or len(sys.argv) != 2:
        print("Usage : BM_API_KEY=... python3 rebuild_orders_by_market.py YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)
    since = sys.argv[1]
    day_start = datetime.datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=PARIS)
    query_date = day_start.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d")

    url = f"https://{HOST}/ws/buyback/v1/orders?creationDate={query_date}&pageSize={PAGE_SIZE}"
    orders, page, total = [], 0, None
    while url:
        page += 1
        data = fetch(url, api_key)
        if data is None:
            print(f"Échec page {page} -> abandon, aucun fichier modifié.", file=sys.stderr)
            sys.exit(1)
        if total is None:
            total = data["count"]
            print(f"{total} commandes depuis {query_date} (UTC), pages de {PAGE_SIZE}.", file=sys.stderr)
        for o in data["results"]:
            local = datetime.datetime.fromisoformat(o["creationDate"].replace("Z", "+00:00")).astimezone(PARIS)
            day = local.strftime("%Y-%m-%d")
            if day < since:
                continue  # le filtre API est en UTC : on borne précisément sur la date locale
            price = o.get("counterOfferPrice") or o.get("originalPrice")
            orders.append((day, local.hour, o["listing"]["title"], o["listing"]["grade"], o["market"],
                           price["value"] if price else None))
        if page % 25 == 0:
            print(f"  page {page}: {len(orders)} commandes retenues", file=sys.stderr)
        url = data.get("next")
        time.sleep(DELAY)

    # garde-fou : une réponse tronquée supprimerait de vrais jours. Le compteur de l'API inclut
    # quelques commandes de la veille UTC (avant minuit à Paris) que l'on écarte volontairement :
    # un écart de quelques % est normal, bien plus ne l'est pas.
    if not orders or len(orders) < 0.95 * total:
        print(f"Seulement {len(orders)} commandes retenues pour {total} annoncées par l'API "
              f"-> abandon, aucun fichier modifié.", file=sys.stderr)
        sys.exit(1)

    vol = load_json("volume_data.json")
    vol.setdefault("markets", [])
    grd_idx = {g: i for i, g in enumerate(vol["grades"])}
    n_dev, n_mk = len(vol["devices"]), len(vol["markets"])

    by_day = defaultdict(lambda: [0, 0.0, 0])    # (day, di, gi, mi)
    by_hour = defaultdict(lambda: [0, 0.0, 0])   # (day, hour, di, gi, mi)
    skipped = 0
    for day, hour, device, grade, market, price in orders:
        label = ORDER_GRADE_TO_LABEL.get(grade)
        if label is None or label not in grd_idx:
            skipped += 1
            continue
        di = ensure_index(vol["devices"], device)
        mi = ensure_index(vol["markets"], market)
        for bucket in (by_day[(day, di, grd_idx[label], mi)], by_hour[(day, hour, di, grd_idx[label], mi)]):
            bucket[0] += 1
            if price is not None:
                bucket[1] += price
                bucket[2] += 1

    # ---- volume_data.json : jours >= since remplacés ----
    old_counts = defaultdict(int)
    for r in vol["rows"]:
        if r[0] >= since:
            old_counts[r[0]] += r[3]
    kept = [r for r in vol["rows"] if r[0] < since]
    new_rows = [[d, di, gi, c, round(s, 2), pc, mi] for (d, di, gi, mi), (c, s, pc) in by_day.items()]
    vol["rows"] = sorted(kept + new_rows)

    # ---- hourly_data.json : détail horaire des jours >= max(since, HOURLY_FROM) ----
    hourly = load_json("hourly_data.json") if os.path.exists("hourly_data.json") else {"days": {}}
    start_hourly = max(since, HOURLY_FROM)
    days = {d: rows for d, rows in hourly["days"].items() if d < start_hourly}
    per_day = defaultdict(list)
    for (day, hour, di, gi, mi), (c, s, pc) in sorted(by_hour.items()):
        if day >= start_hourly:
            per_day[day].append([hour, di, gi, c, round(s, 2), pc, mi])
    days.update(per_day)
    hourly["days"] = dict(sorted(days.items()))

    save_json("volume_data.json", vol)
    save_json("hourly_data.json", hourly)

    new_counts = defaultdict(int)
    for r in new_rows:
        new_counts[r[0]] += r[3]
    by_market = defaultdict(int)
    for (_d, _di, _gi, mi), (c, _s, _pc) in by_day.items():
        by_market[vol["markets"][mi]] += c
    changed = sorted((d, old_counts.get(d, 0), new_counts[d]) for d in new_counts if old_counts.get(d, 0) != new_counts[d])
    print(f"{len(orders)} commandes ({skipped} ignorées, grade hors libellés officiels) -> "
          f"{len(new_rows)} lignes jour, {sum(len(v) for v in per_day.values())} lignes horaires sur {len(per_day)} jour(s).")
    print(f"Pays : {dict(sorted(by_market.items()))} | +{len(vol['devices']) - n_dev} appareil(s), "
          f"+{len(vol['markets']) - n_mk} pays ajouté(s) à la liste.")
    print(f"Jours dont le total change vs avant ({len(changed)}) [jour, avant, après] :")
    for d, a, b in changed[:40]:
        print(f"  {d}: {a} -> {b}")


if __name__ == "__main__":
    main()
