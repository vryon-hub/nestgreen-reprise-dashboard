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

# alerte email si les annonces BackMarket semblent hors ligne en masse (cas
# réel du 28/08/2026) ; ne renvoie qu'au début de l'incident (alert_state.json).
python3 check_listings_offline_alert.py

python3 append_backbox_history.py
python3 build_backbox_history_data.py
python3 build_backbox_raw_by_day.py

python3 fetch_today_hourly.py
python3 build_hourly_data.py
python3 merge_today_into_volume.py

# alerte email si 500 reprises atteintes aujourd'hui (heure de Paris) ; ne
# renvoie qu'une fois/jour (alert_state.json). GMAIL_USER/GMAIL_APP_PASSWORD
# injectés depuis les Secrets GitHub -> ne pas définir en dur ici.
python3 check_reprises_alert.py

python3 build_combined_dashboard.py

echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Rafraîchissement terminé"
