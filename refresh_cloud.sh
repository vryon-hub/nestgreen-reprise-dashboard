#!/bin/bash
# Rafraîchit les prix BackBox + le détail par cycle + le tableau Prix, et
# reconstruit combined_dashboard.html. Tourne dans GitHub Actions (voir
# .github/workflows/refresh.yml), pas sur le Mac de Nestgreen.
#
# BM_API_KEY est injectée par GitHub Actions depuis les Secrets du dépôt —
# jamais écrite en dur ici (contrairement à l'ancien refresh_prix.sh local).
#
# Onglet Volume (volume_data.json, status_data.json, payment_delay_data.json)
# PAS touché ici -> reste figé sur son dernier état local tant que la phase 2
# (migration du job quotidien, plus lourd) n'est pas faite.

set -euo pipefail
cd "$(dirname "$0")"

: "${BM_API_KEY:?BM_API_KEY manquante (secret GitHub Actions non injecté ?)}"
export BM_API_KEY

echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Rafraîchissement démarré"

python3 extract_buyback_listings.py
python3 fetch_competitors.py
python3 build_dashboard_data.py

python3 append_backbox_history.py
python3 build_backbox_history_data.py
python3 build_backbox_raw_by_day.py

python3 fetch_today_hourly.py
python3 build_hourly_data.py
python3 merge_today_into_volume.py

python3 build_combined_dashboard.py

echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Rafraîchissement terminé"
