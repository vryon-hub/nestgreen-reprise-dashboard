#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alerte email si une grosse part des listings BackMarket sort d'un coup hors
ligne (statut "OFFLINE in 4 markets") -> cas réel observé le 28/08/2026 :
677/711 listings avec statut BackBox habituellement, tombé à 0/711 pendant
~1h. Nestgreen ne reçoit alors plus AUCUNE proposition de reprise tant que
ça dure.

Détection : dashboard_data.json (reconstruit à chaque cycle par
build_dashboard_data.py) ne porte la clé "w" (statut BackBox live) que sur
les listings pour lesquels l'API competitors a répondu -> une chute brutale
de ce taux signale l'incident, pas juste les quelques produits
volontairement désactivés au jour le jour (~5% en temps normal).

Ne renvoie qu'un email au DÉBUT de l'incident (alert_state.json garde un
drapeau), pas un à chaque cycle de 15 min tant que ça dure. Le drapeau se
remet à zéro dès que le taux redevient normal, pour re-alerter au prochain
incident.
"""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from check_reprises_alert import send_email  # réutilise l'envoi SMTP déjà validé
from competitor_snapshot import update_last_known_good, freeze_snapshot

PARIS = ZoneInfo("Europe/Paris")
HERE = Path(__file__).parent

DASHBOARD_DATA = HERE / "dashboard_data.json"
STATE_PATH = HERE / "alert_state.json"
ONLINE_RATIO_THRESHOLD = 0.5  # en dessous de 50% de listings avec statut BackBox -> anomalie


def build_email_html(with_status, total, pct, detected_at):
    return f"""<div style="background:#FAFAFA;padding:32px 16px;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#FFFFFF;border-radius:12px;overflow:hidden;border:1px solid #E5E5E0;">
    <tr>
      <td style="background:#C43D3D;padding:20px 28px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="font-size:15px;font-weight:700;color:#FFFFFF;letter-spacing:0.02em;">Nestgreen</td>
            <td style="text-align:right;font-size:13px;color:#FBE6E6;">Grille Reprise</td>
          </tr>
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:32px 28px 8px;">
        <p style="margin:0;font-size:13px;font-weight:600;color:#C43D3D;text-transform:uppercase;letter-spacing:0.05em;">Incident détecté</p>
        <h1 style="margin:8px 0 0;font-size:24px;line-height:1.3;color:#242424;font-weight:700;">Les annonces BackMarket semblent hors ligne</h1>
        <p style="margin:8px 0 0;font-size:14px;color:#5B6560;">détecté le {detected_at} &middot; heure de Paris</p>
      </td>
    </tr>
    <tr>
      <td style="padding:20px 28px 8px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td width="50%" style="background:#F0F4F1;border-radius:10px;padding:16px 18px;">
              <p style="margin:0;font-size:11.5px;font-weight:600;color:#8B948E;text-transform:uppercase;letter-spacing:0.05em;">Listings avec statut</p>
              <p style="margin:6px 0 0;font-size:28px;font-weight:700;color:#242424;">{with_status} / {total}</p>
            </td>
            <td width="12"></td>
            <td width="50%" style="background:#F0F4F1;border-radius:10px;padding:16px 18px;">
              <p style="margin:0;font-size:11.5px;font-weight:600;color:#8B948E;text-transform:uppercase;letter-spacing:0.05em;">Taux en ligne</p>
              <p style="margin:6px 0 0;font-size:28px;font-weight:700;color:#C43D3D;">{pct:.0f}%</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:20px 28px 28px;">
        <p style="margin:0;font-size:13.5px;line-height:1.6;color:#5B6560;">
          En temps normal, environ 95% des listings ont un statut BackBox actif. Ce taux est nettement en dessous — Nestgreen ne reçoit probablement plus aucune proposition de reprise sur BackMarket en ce moment. Un incident similaire le 28/08/2026 a duré environ une heure. Vérifiez le Seller Center BackMarket.
        </p>
      </td>
    </tr>
    <tr>
      <td style="padding:16px 28px;border-top:1px solid #E5E5E0;">
        <p style="margin:0;font-size:12px;color:#8B948E;">Alerte automatique &middot; Grille Reprise Nestgreen</p>
      </td>
    </tr>
  </table>
</div>"""


def main():
    if not DASHBOARD_DATA.exists():
        print("dashboard_data.json absent, on saute.")
        return

    data = json.loads(DASHBOARD_DATA.read_text(encoding="utf-8"))
    rows = data["rows"]
    total = len(rows)
    with_status = sum(1 for r in rows if r.get("w"))
    pct = (with_status / total * 100) if total else 0

    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    is_incident = total > 0 and (with_status / total) < ONLINE_RATIO_THRESHOLD

    if not is_incident:
        update_last_known_good()  # état sain -> devient la référence si un incident démarre juste après
        if state.get("listings_offline_alerted"):
            print(f"Taux revenu à la normale ({with_status}/{total}, {pct:.0f}%) -> réarmement de l'alerte.")
            state["listings_offline_alerted"] = False
            STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
        else:
            print(f"{with_status}/{total} listings avec statut ({pct:.0f}%), normal.")
        return

    if state.get("listings_offline_alerted"):
        print(f"Incident toujours en cours ({with_status}/{total}, {pct:.0f}%), déjà alerté, pas de renvoi.")
        return

    # fige les prix concurrents (repère/ptw) du dernier cycle sain, avant que
    # dashboard_data.json ne finisse par n'avoir plus aucune donnée à comparer
    snapshot_path = freeze_snapshot("hors_ligne")
    print(f"Prix concurrents figés dans {snapshot_path}" if snapshot_path else "Pas d'état sain antérieur à figer.")

    detected_at = datetime.now(PARIS).strftime("%d/%m/%Y à %H:%M")
    html = build_email_html(with_status, total, pct, detected_at)
    send_email("Nestgreen - Annonces BackMarket probablement hors ligne", html)

    state["listings_offline_alerted"] = True
    STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
    print(f"Alerte incident envoyée : {with_status}/{total} listings avec statut ({pct:.0f}%).")


if __name__ == "__main__":
    main()
