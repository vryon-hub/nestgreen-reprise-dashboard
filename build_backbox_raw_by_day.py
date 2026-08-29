#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Éclate backbox_history.jsonl (un échantillon par cycle de rafraîchissement,
par listing et par marché) en un fichier JSON compact PAR JOUR, pour le
détail "clique sur une heure pour voir les appels du cycle" du dashboard.

Pourquoi un fichier par jour plutôt que tout intégrer dans la page : au
rythme de rafraîchissement (15-30 min), l'historique complet grossit vite
(plusieurs Mo par jour) -> l'embarquer en dur dans combined_dashboard.html
ferait exploser sa taille alors que ce niveau de détail n'est consulté
qu'au clic, pour un jour précis. Chaque fichier backbox_raw/YYYY-MM-DD.json
est chargé à la demande par le navigateur (même serveur HTTP local que le
dashboard), pas au chargement de la page.

Mêmes filtres qu'ailleurs : exclut les échantillons sans prix confirmé
(placeholder <= 1€, ou legacy sans suivi de prix).
"""
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
HISTORY = HERE / "backbox_history.jsonl"
DASHBOARD_DATA = HERE / "dashboard_data.json"
OUT_DIR = HERE / "backbox_raw"

MARKETS = ["DE", "ES", "FR", "IT"]
NO_PRICE_THRESHOLD = 1.0


def main():
    if not HISTORY.exists():
        print("Pas d'historique encore (backbox_history.jsonl absent).")
        return

    dashboard = json.loads(DASHBOARD_DATA.read_text(encoding="utf-8"))
    sku_map = {r["sku"]: (r["device"], r["g"]) for r in dashboard["rows"] if r.get("device")}
    grade_labels = dashboard["gradeLabels"]
    devices = sorted({d for d, _ in sku_map.values()})
    dev_idx = {d: i for i, d in enumerate(devices)}

    by_day = defaultdict(list)  # "YYYY-MM-DD" -> [[ts, di, gi, mi, ptw, price, win], ...]
    n_lines = 0
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        n_lines += 1
        rec = json.loads(line)
        day = rec["ts"][:10]
        for sku, wins in rec["w"].items():
            info = sku_map.get(sku)
            if info is None:
                continue
            device, gi = info
            di = dev_idx[device]
            for market, v in wins.items():
                if market not in MARKETS:
                    continue
                if not isinstance(v, list):
                    continue
                win, ptw, price = v
                if price is None or price <= NO_PRICE_THRESHOLD:
                    continue
                by_day[day].append([rec["ts"], di, gi, MARKETS.index(market), ptw, price, win])

    OUT_DIR.mkdir(exist_ok=True)
    for day, rows in by_day.items():
        out = {"devices": devices, "grades": grade_labels, "markets": MARKETS, "rows": rows}
        (OUT_DIR / f"{day}.json").write_text(
            json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    total_rows = sum(len(r) for r in by_day.values())
    print(f"{n_lines} cycles -> {len(by_day)} jour(s) écrits dans {OUT_DIR}/ ({total_rows} lignes au total)")


if __name__ == "__main__":
    main()
