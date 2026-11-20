#!/usr/bin/env python3
"""
Agrège today_hourly.json en lignes compactes
[hour, deviceIdx, gradeIdx, count, priceSum, priceCount, marketIdx],
en réutilisant les MÊMES index devices/grades/marchés que volume_data.json pour rester
cohérent avec les filtres (recherche appareil, chips grade, chips pays) déjà rendus côté page.

Un appareil ou un pays encore inconnu de volume_data.json y est AJOUTÉ en fin de liste
(les index déjà utilisés ne bougent jamais) au lieu d'être ignoré : sinon ses commandes
disparaîtraient des totaux.

hourly_data.json garde l'historique heure par heure de CHAQUE jour déjà traité
(pas seulement le jour de génération) : {"days": {"YYYY-MM-DD": [rows...]}}.
Le jour courant est réécrit à chaque cycle (il se complète au fil de la journée) ;
les jours précédents restent tels qu'ils étaient à leur dernière heure suivie.
"""
import json
from collections import defaultdict
from pathlib import Path

from grade_mapping import ORDER_GRADE_TO_LABEL
from volume_common import ensure_index, load_json, save_json

OUT = Path('hourly_data.json')

vol = load_json('volume_data.json')
vol.setdefault('markets', [])
n_devices, n_markets = len(vol['devices']), len(vol['markets'])
grades = vol['grades']  # déjà des libellés officiels (voir build_volume_data.py)
grd_idx = {g: i for i, g in enumerate(grades)}

data = load_json('today_hourly.json')
records = data['records']

agg = defaultdict(lambda: [0, 0.0, 0])  # (hour, devIdx, gradeIdx, marketIdx) -> [count, priceSum, priceCount]
skipped = 0
for r in records:
    label = ORDER_GRADE_TO_LABEL.get(r['grade'])
    # un grade hors des 6 libellés officiels est ignoré (étendre la liste casserait l'ordre/les couleurs)
    if label is None or label not in grd_idx:
        skipped += 1
        continue
    key = (r['hour'], ensure_index(vol['devices'], r['device']), grd_idx[label],
           ensure_index(vol['markets'], r['market']))
    agg[key][0] += 1
    if r['price'] is not None:
        agg[key][1] += r['price']
        agg[key][2] += 1

rows = [[h, di, gi, c, round(s, 2), pc, mi] for (h, di, gi, mi), (c, s, pc) in sorted(agg.items())]

if len(vol['devices']) != n_devices or len(vol['markets']) != n_markets:
    save_json('volume_data.json', vol)
    print(f"volume_data.json : +{len(vol['devices']) - n_devices} appareil(s), +{len(vol['markets']) - n_markets} pays ajouté(s)")

if OUT.exists():
    existing = json.loads(OUT.read_text(encoding='utf-8'))
    days = existing.get('days')
    if days is None:
        # ancien format {"date": ..., "rows": ...} d'avant la persistance multi-jours
        days = {existing['date']: existing['rows']} if 'date' in existing else {}
else:
    days = {}
days[data['date']] = rows

save_json(str(OUT), {'days': days})
print(f"{len(records)} commandes -> {len(rows)} lignes ({skipped} ignorées, grade hors libellés officiels), "
      f"{len(days)} jour(s) au total dans hourly_data.json")
