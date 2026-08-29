#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Garde une trace des prix concurrents (repère/price_to_win) au moment où on
en perd la visibilité (annonces hors ligne) ou au moment où on atteint un
seuil surveillé (500 reprises/jour) — dans les deux cas, dashboard_data.json
peut être écrasé au cycle suivant avant qu'on ait eu le temps de comparer,
donc on fige une copie plutôt que de laisser l'info disparaître.

- update_last_known_good() : à appeler à chaque cycle SAIN (annonces en
  ligne), garde une copie glissante du dernier état connu -> c'est CETTE
  copie qui sera figée si un incident démarre juste après (le cycle en
  incident lui-même n'a plus de prix concurrents à observer).
- freeze_snapshot(tag) : fige une copie datée du dernier état sain connu
  dans incident_snapshots/, appelé au moment précis où un incident/seuil
  est détecté.
"""
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
HERE = Path(__file__).parent

DASHBOARD_DATA = HERE / "dashboard_data.json"
LAST_GOOD = HERE / "last_known_good_dashboard_data.json"
SNAPSHOTS_DIR = HERE / "incident_snapshots"


def update_last_known_good():
    if DASHBOARD_DATA.exists():
        shutil.copy(DASHBOARD_DATA, LAST_GOOD)


def freeze_snapshot(tag):
    """Retourne le chemin du snapshot créé, ou None si aucun état sain
    n'était disponible à figer (ex: tout premier cycle)."""
    if not LAST_GOOD.exists():
        return None
    SNAPSHOTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(PARIS).strftime("%Y-%m-%dT%H%M")
    dest = SNAPSHOTS_DIR / f"{ts}_{tag}.json"
    shutil.copy(LAST_GOOD, dest)
    return dest
