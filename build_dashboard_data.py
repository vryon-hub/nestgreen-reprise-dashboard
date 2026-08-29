#!/usr/bin/env python3
"""
Reconstruit dashboard_data.json à partir de buyback_listings.json + competitors.json
(si présent) + decode_sku.py.
"""
import json
import re

from decode_sku import decode_base

GRADE_ORDER = {
    # Même ordre que le back-office BackMarket : meilleur état en premier.
    'FUNCTIONAL_FLAWLESS': 0,
    'FUNCTIONAL_GOOD': 1,
    'FUNCTIONAL_USED': 2,
    'FUNCTIONAL_CRACKED': 3,
    'NOT_FUNCTIONAL_USED': 4,
    'NOT_FUNCTIONAL_CRACKED': 5,
}
GRADE_LABEL = {
    # Libellés officiels BackMarket (back-office), pas une reformulation maison.
    'NOT_FUNCTIONAL_CRACKED': 'Non fonctionnel - Cassé',
    'NOT_FUNCTIONAL_USED': 'Non fonctionnel - État correct',
    'FUNCTIONAL_CRACKED': 'Fonctionnel - Cassé',
    'FUNCTIONAL_USED': 'Fonctionnel - État correct',
    'FUNCTIONAL_GOOD': 'Fonctionnel - Très bon état',
    'FUNCTIONAL_FLAWLESS': 'Fonctionnel - Parfait état',
}


def device_for(sku):
    if not sku or sku == 'None':
        return None, None
    base = re.sub(r'G1?[A-F]$', '', sku)
    brand, name, _ = decode_base(base)
    if name is None or 'non reconnu' in name:
        return brand, None
    return brand, name


def build_productid_fallback(data):
    """productId -> (brand, device) déduit d'une listing sœur (même productId) qui a
    un SKU exploitable. Couvre les grades 'non fonctionnel' qui n'ont souvent pas de
    SKU propre chez Nestgreen, alors que les grades fonctionnels du même modèle si."""
    fallback = {}
    for l in data:
        brand, device = device_for(l['sku'])
        if device and l['productId'] not in fallback:
            fallback[l['productId']] = (brand, device)
    return fallback


def main():
    data = json.load(open('buyback_listings.json', encoding='utf-8'))
    try:
        competitors = json.load(open('competitors.json', encoding='utf-8'))
    except FileNotFoundError:
        competitors = {}

    pid_fallback = build_productid_fallback(data)

    rows = []
    markets = set()
    brands = set()
    for l in data:
        prices = {m: float(p['amount']) for m, p in l['prices'].items()}
        markets |= set(prices.keys())
        brand, device = device_for(l['sku'])
        if device is None and l['productId'] in pid_fallback:
            brand, device = pid_fallback[l['productId']]
        if brand:
            brands.add(brand)
        row = {
            'sku': l['sku'] or 'pas de SKU (BackMarket)',
            'brand': brand,
            'device': device,
            'g': GRADE_ORDER[l['aestheticGradeCode']],
            'p': prices,
        }
        comp = competitors.get(l['id'])
        if comp:
            row['w'] = {
                c['market']: {'win': c['is_winning'], 'ptw': c['price_to_win']}
                for c in comp
            }
        rows.append(row)

    markets = sorted(markets)
    rows.sort(key=lambda r: ((r['brand'] or 'zzz'), (r['device'] or 'zzz'), r['g']))
    out = {
        'markets': markets,
        'gradeLabels': [GRADE_LABEL[k] for k, _ in sorted(GRADE_ORDER.items(), key=lambda kv: kv[1])],
        'brands': sorted(brands),
        'rows': rows,
    }
    json.dump(out, open('dashboard_data.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

    with_win = sum(1 for r in rows if 'w' in r)
    print(f'rows: {len(rows)}, avec statut BackBox: {with_win}')


if __name__ == '__main__':
    main()
