#!/usr/bin/env python3
"""
Décodeur best-effort du SKU interne Nestgreen -> nom d'appareil lisible.
Reverse-engineered à partir des 566 SKU observés dans le catalogue buyback (2026-08-26).
Pas une source officielle : à valider par Nestgreen, cas par cas si besoin.
"""
import re

IPHONE_SUFFIX_RULES = [
    # (regex sur le reste après "IP", nom du modèle)
    (r'^AIR$', 'iPhone Air'),
    (r'^XR$', 'iPhone XR'),
    (r'^SE2022$', 'iPhone SE (2022)'),
    (r'^SE20$', 'iPhone SE (2020)'),
    (r'^(\d+)MINI$', lambda m: f'iPhone {m.group(1)} Mini'),
    (r'^(\d+)M$', lambda m: f'iPhone {m.group(1)} Mini'),
    (r'^(\d+)PM$', lambda m: f'iPhone {m.group(1)} Pro Max'),
    (r'^(\d+)PL(US)?$', lambda m: f'iPhone {m.group(1)} Plus'),
    (r'^(\d+)P$', lambda m: f'iPhone {m.group(1)} Pro'),
    (r'^(\d+)E$', lambda m: f'iPhone {m.group(1)}e'),
    (r'^(\d+)$', lambda m: f'iPhone {m.group(1)}'),
]

SAMSUNG_RULES = [
    # RSGS = Galaxy S-series, RSGA/RGA = Galaxy A-series
    (r'^SGS(\d+)U$', lambda m: f'Galaxy S{m.group(1)} Ultra'),
    (r'^SGS(\d+)PLUS$', lambda m: f'Galaxy S{m.group(1)}+'),
    (r'^SGS(\d+)P$', lambda m: f'Galaxy S{m.group(1)}+'),
    (r'^SGS(\d+)FE$', lambda m: f'Galaxy S{m.group(1)} FE'),
    (r'^SGS(\d+)$', lambda m: f'Galaxy S{m.group(1)}'),
    (r'^S?GA(\d+)$', lambda m: f'Galaxy A{m.group(1)}'),
]


def decode_base(base):
    """base = SKU sans le suffixe de grade (ex: RIP14PM1024, RSGS23U256)."""
    m = re.match(r'^([AR])(IP|SGS|SGA|GA)(.*)$', base)
    if not m:
        return None, None, base
    _, family, rest = m.groups()

    # capacité = valeur connue en fin de chaîne (avec marqueur réseau optionnel 4G/5G juste avant) ;
    # on ne peut pas prendre "tous les chiffres finaux" car modèle et capacité sont tous deux numériques
    # et concaténés sans séparateur (ex: RIP11128 = modèle "11" + capacité "128").
    cap_m = re.search(r'(?:([45]G))?(64|128|256|512|1024|2048)$', rest)
    if not cap_m:
        return None, None, base
    network, capacity = cap_m.groups()
    model_part = rest[:cap_m.start()]

    if family == 'IP':
        full = model_part
        for pattern, label in IPHONE_SUFFIX_RULES:
            mm = re.match(pattern, full)
            if mm:
                name = label(mm) if callable(label) else label
                return 'Apple', f'{name} {capacity} Go', base
        return 'Apple', f'iPhone ({model_part}) {capacity} Go — non reconnu', base

    else:
        full = family + model_part
        for pattern, label in SAMSUNG_RULES:
            mm = re.match(pattern, full)
            if mm:
                name = label(mm) if callable(label) else label
                net = f' {network}' if network else ''
                return 'Samsung', f'{name}{net} {capacity} Go', base
        return 'Samsung', f'Galaxy ({model_part}) {capacity} Go — non reconnu', base


if __name__ == '__main__':
    import json
    data = json.load(open('buyback_listings.json'))
    bases = sorted(set(re.sub(r'G1?[A-F]$', '', l['sku']) for l in data if l['sku'] and l['sku'] != 'None'))
    for b in bases:
        brand, name, _ = decode_base(b)
        flag = '  <-- À VÉRIFIER' if (not name or 'non reconnu' in (name or '')) else ''
        print(f'{b:20s} -> {brand or "?":8s} {name}{flag}')
