#!/usr/bin/env python3
"""
Agrège today_hourly.json en lignes compactes [hour, deviceIdx, gradeIdx, count, priceSum, priceCount],
en réutilisant les MÊMES index devices/grades que volume_data.json pour rester cohérent
avec les filtres (recherche appareil, chips grade) déjà rendus côté page.

hourly_data.json garde l'historique heure par heure de CHAQUE jour déjà traité
(pas seulement le jour de génération) : {"days": {"YYYY-MM-DD": [rows...]}}.
Le jour courant est réécrit à chaque cycle (il se complète au fil de la journée) ;
les jours précédents restent tels qu'ils étaient à leur dernière heure suivie.
"""
import json
from collections import defaultdict
from pathlib import Path

from grade_mapping import ORDER_GRADE_TO_LABEL

OUT = Path('hourly_data.json')

vol = json.load(open('volume_data.json', encoding='utf-8'))
devices = vol['devices']
grades = vol['grades']  # déjà des libellés officiels (voir build_volume_data.py)
dev_idx = {d: i for i, d in enumerate(devices)}
grd_idx = {g: i for i, g in enumerate(grades)}

data = json.load(open('today_hourly.json', encoding='utf-8'))
records = data['records']

agg = defaultdict(lambda: [0, 0.0, 0])  # (hour, devIdx, gradeIdx) -> [count, priceSum, priceCount]
skipped = 0
for r in records:
    label = ORDER_GRADE_TO_LABEL.get(r['grade'])
    # on réutilise STRICTEMENT les index de volume_data.json (déjà rendus en chips côté page) ;
    # un appareil/grade absent de l'historique annuel est ignoré plutôt que d'étendre les listes
    # (qui casserait la correspondance d'index avec les chips déjà affichées).
    if r['device'] not in dev_idx or label is None or label not in grd_idx:
        skipped += 1
        continue
    key = (r['hour'], dev_idx[r['device']], grd_idx[label])
    agg[key][0] += 1
    if r['price'] is not None:
        agg[key][1] += r['price']
        agg[key][2] += 1

rows = [[h, di, gi, c, round(s, 2), pc] for (h, di, gi), (c, s, pc) in sorted(agg.items())]

if OUT.exists():
    existing = json.loads(OUT.read_text(encoding='utf-8'))
    days = existing.get('days')
    if days is None:
        # ancien format {"date": ..., "rows": ...} d'avant la persistance multi-jours
        days = {existing['date']: existing['rows']} if 'date' in existing else {}
else:
    days = {}
days[data['date']] = rows

out = {'days': days}
OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print(f"{len(records)} commandes -> {len(rows)} lignes ({skipped} ignorées, appareil/grade absent de l'historique annuel), "
      f"{len(days)} jour(s) au total dans hourly_data.json")
