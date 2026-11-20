#!/usr/bin/env python3
"""
Injecte le total du jour (hourly_data.json, sommé sur toutes les heures)
comme lignes du jour dans volume_data.json, pour que les vues Semaine/Mois/
Année incluent aussi la journée en cours (pas seulement la vue Jour).

Lignes : [date, deviceIdx, gradeIdx, count, priceSum, priceCount, marketIdx]
(une ligne par appareil × grade × pays d'achat).

Remplace toute ligne déjà présente pour la date du jour avant de rajouter
les totaux frais, pour rester idempotent d'un cycle de rafraîchissement à
l'autre.
"""
from collections import defaultdict

from volume_common import load_json, save_json

vol = load_json('volume_data.json')
hourly = load_json('hourly_data.json')
today = load_json('today_hourly.json')['date']

# retire toute ligne déjà présente pour aujourd'hui (ré-écriture idempotente)
rows = [r for r in vol['rows'] if r[0] != today]

agg = defaultdict(lambda: [0, 0.0, 0])  # (deviceIdx, gradeIdx, marketIdx) -> [count, priceSum, priceCount]
for row in hourly['days'].get(today, []):
    _hour, di, gi, c, s, pc = row[:6]
    mi = row[6] if len(row) > 6 else None
    a = agg[(di, gi, mi)]
    a[0] += c
    a[1] += s
    a[2] += pc

for (di, gi, mi), (c, s, pc) in agg.items():
    rows.append([today, di, gi, c, round(s, 2), pc] + ([] if mi is None else [mi]))

vol['rows'] = sorted(rows)
save_json('volume_data.json', vol)
print(f"Jour {today} injecté dans volume_data.json ({len(agg)} lignes appareil/grade/pays, "
      f"{sum(a[0] for a in agg.values())} commandes).")
