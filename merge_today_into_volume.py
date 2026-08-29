#!/usr/bin/env python3
"""
Injecte le total du jour (hourly_data.json, sommé sur toutes les heures)
comme ligne du jour dans volume_data.json, pour que les vues Semaine/Mois/
Année incluent aussi la journée en cours (pas seulement la vue Jour).

Remplace toute ligne déjà présente pour la date du jour avant de rajouter
les totaux frais, pour rester idempotent d'un cycle de rafraîchissement à
l'autre (appelé toutes les 30 min par refresh_prix.sh).
"""
import json
from collections import defaultdict

vol = json.load(open('volume_data.json', encoding='utf-8'))
hourly = json.load(open('hourly_data.json', encoding='utf-8'))
today = json.load(open('today_hourly.json', encoding='utf-8'))['date']

# retire toute ligne déjà présente pour aujourd'hui (ré-écriture idempotente)
rows = [r for r in vol['rows'] if r[0] != today]

agg = defaultdict(lambda: [0, 0.0, 0])  # (deviceIdx, gradeIdx) -> [count, priceSum, priceCount]
for _hour, di, gi, c, s, pc in hourly['days'].get(today, []):
    a = agg[(di, gi)]
    a[0] += c
    a[1] += s
    a[2] += pc

for (di, gi), (c, s, pc) in agg.items():
    rows.append([today, di, gi, c, round(s, 2), pc])

vol['rows'] = sorted(rows)
json.dump(vol, open('volume_data.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(f"Jour {today} injecté dans volume_data.json ({len(agg)} couples appareil/grade, "
      f"{sum(a[0] for a in agg.values())} commandes).")
