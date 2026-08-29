#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agrège backbox_history.jsonl (un échantillon toutes les 30 min par listing
et par marché depuis le lancement du suivi) en lignes compactes par HEURE,
pour le panneau "Historique BackBox" du dashboard Prix : % de temps gagné,
et courbes "prix pour gagner la BackBox" vs "votre prix".

Le mapping SKU -> device/grade vient de dashboard_data.json (mapping stable
tant que buyback_listings.json ne change pas).

Exclut les échantillons sans prix confirmé > 1€ : les tout premiers cycles
(avant l'ajout du suivi de prix) et les prix <= 1€ (placeholder BackMarket
"pas de prix engagé", toujours perdant) ne comptent ni dans le %, ni dans les
courbes de prix — un prix inconnu ou factice fausserait le taux de BackBox
sans rapport avec la compétition réelle.
"""
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
HISTORY = HERE / "backbox_history.jsonl"
DASHBOARD_DATA = HERE / "dashboard_data.json"
OUT = HERE / "backbox_history_data.json"

MARKETS = ["DE", "ES", "FR", "IT"]
NO_PRICE_THRESHOLD = 1.0  # <= ce montant = placeholder, pas un vrai prix


def main():
    dashboard = json.loads(DASHBOARD_DATA.read_text(encoding="utf-8"))
    sku_map = {r["sku"]: (r["device"], r["g"]) for r in dashboard["rows"] if r.get("device")}
    grade_labels = dashboard["gradeLabels"]

    devices = sorted({d for d, _ in sku_map.values()})
    dev_idx = {d: i for i, d in enumerate(devices)}

    if not HISTORY.exists():
        out = {"devices": devices, "grades": grade_labels, "markets": MARKETS, "rows": []}
        OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print("Pas d'historique encore (backbox_history.jsonl absent).")
        return

    # (heure "YYYY-MM-DDTHH", deviceIdx, gradeIdx, marketIdx) ->
    #   [samples, wins, ptw_sum, ptw_n, price_sum, price_n]
    agg = defaultdict(lambda: [0, 0, 0.0, 0, 0.0, 0])
    skipped_sku = 0
    n_lines = 0
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        n_lines += 1
        rec = json.loads(line)
        hour = rec["ts"][:13]  # "YYYY-MM-DDTHH"
        for sku, wins in rec["w"].items():
            info = sku_map.get(sku)
            if info is None:
                skipped_sku += 1
                continue
            device, gi = info
            di = dev_idx[device]
            for market, v in wins.items():
                if market not in MARKETS:
                    continue
                if isinstance(v, list):
                    win, ptw, price = v
                else:
                    win, ptw, price = (1 if v else 0), None, None
                # prix inconnu (tout premiers échantillons, avant l'ajout du suivi de prix)
                # ou <= 1€ (placeholder BackMarket) -> pas un prix confirmé, on exclut.
                if price is None or price <= NO_PRICE_THRESHOLD:
                    continue
                key = (hour, di, gi, MARKETS.index(market))
                a = agg[key]
                a[0] += 1
                a[1] += win
                if ptw is not None:
                    a[2] += ptw
                    a[3] += 1
                if price is not None:
                    a[4] += price
                    a[5] += 1

    rows = [[h, di, gi, mi, s, w, round(ps, 2), pn, round(prs, 2), prn]
            for (h, di, gi, mi), (s, w, ps, pn, prs, prn) in sorted(agg.items())]
    out = {"devices": devices, "grades": grade_labels, "markets": MARKETS, "rows": rows}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{n_lines} cycles archivés -> {len(rows)} lignes agrégées (par heure), "
          f"{len(devices)} appareils ({skipped_sku} échantillons SKU non mappé ignorés).")


if __name__ == "__main__":
    main()
