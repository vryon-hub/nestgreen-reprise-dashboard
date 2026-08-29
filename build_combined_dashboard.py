#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Assemble combined_dashboard.html à partir de combined_template.html en
injectant les JSON de données. Utilisé après un rafraîchissement de
dashboard_data.json (prix/BackBox) pour reconstruire le fichier servi
localement, sans dépendre du contexte d'une session Claude.
"""
import os
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent

PLACEHOLDERS = {
    "__PRIX_DATA_JSON__": HERE / "dashboard_data.json",
    "__BACKBOX_HISTORY_DATA_JSON__": HERE / "backbox_history_data.json",
    # snapshot statique, pas rebuild ici (dépend d'un Excel 150+ Mo côté KPI200,
    # hors de portée du dépôt cloud) -> à mettre à jour manuellement si besoin.
    "__MARGIN_DATA_JSON__": HERE / "margin_data.json",
    "__VOLUME_DATA_JSON__": HERE / "volume_data.json",
    "__HOURLY_DATA_JSON__": HERE / "hourly_data.json",
    "__STATUS_DATA_JSON__": HERE / "status_data.json",
    "__PAYMENT_DELAY_DATA_JSON__": HERE / "payment_delay_data.json",
}


def main():
    html = (HERE / "combined_template.html").read_text(encoding="utf-8")
    for placeholder, path in PLACEHOLDERS.items():
        html = html.replace(placeholder, path.read_text(encoding="utf-8"))
    html = html.replace("__BUILT_AT__", datetime.now().strftime("%d/%m/%Y à %H:%M"))

    remaining = [p for p in PLACEHOLDERS if p in html]
    if remaining:
        raise SystemExit(f"Placeholders non résolus : {remaining}")

    out = HERE / "index.html"  # GitHub Pages sert index.html à la racine par défaut
    tmp = out.with_suffix(".html.tmp")
    tmp.write_text(html, encoding="utf-8")
    os.replace(tmp, out)  # écriture atomique : jamais de lecture d'un fichier à moitié écrit
    print(f"Écrit dans {out} ({len(html):,} octets)")


if __name__ == "__main__":
    main()
