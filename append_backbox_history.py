#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ajoute une ligne d'historique BackBox à backbox_history.jsonl à partir du
dashboard_data.json qui vient d'être reconstruit (un échantillon "gagné/perdu"
+ prix pour gagner + votre prix, par listing et par marché, toutes les 30 min
via refresh_prix.sh).

Ne remonte PAS dans le passé : le suivi ne démarre qu'à partir du premier
appel de ce script. Format compact en JSON Lines (une ligne = un cycle),
clé par SKU pour rester robuste si l'ordre des listings change un jour.
Chaque marché -> [win(0/1), ptw, prix] (ptw = prix pour gagner la BackBox,
prix = votre prix actuel sur ce listing/marché).

Les marchés à 1,00 € (placeholder BackMarket = "pas de prix engagé", pas un
vrai prix de reprise) sont exclus : ils sont structurellement toujours
perdants et fausseraient le taux de BackBox sans rapport avec la compétition
réelle (cas typique des grades "Non fonctionnel").
"""
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
DASHBOARD_DATA = HERE / "dashboard_data.json"
HISTORY = HERE / "backbox_history.jsonl"
NO_PRICE_THRESHOLD = 1.0  # <= ce montant = placeholder, pas un vrai prix


def main():
    data = json.loads(DASHBOARD_DATA.read_text(encoding="utf-8"))
    listings = {}
    for r in data["rows"]:
        if not r.get("w"):
            continue
        markets = {
            m: [1 if v["win"] else 0, v["ptw"], r["p"].get(m)]
            for m, v in r["w"].items()
            if r["p"].get(m) is not None and r["p"][m] > NO_PRICE_THRESHOLD
        }
        if markets:
            listings[r["sku"]] = markets

    line = {"ts": datetime.now().isoformat(timespec="seconds"), "w": listings}
    with open(HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n")

    print(f"Historique BackBox : +1 échantillon ({len(listings)} listings), "
          f"{HISTORY.stat().st_size / 1024:.0f} Ko au total.")


if __name__ == "__main__":
    main()
