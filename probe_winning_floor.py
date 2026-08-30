#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sur un listing où Nestgreen gagne déjà la BackBox, price_to_win renvoie
systématiquement le prix actuel (masqué) au lieu du vrai seuil concurrent
(cf mémoire buyback_backmarket_project.md, confirmé 26/08 et 30/08/2026).
On ne peut voir le vrai seuil qu'en perdant temporairement.

Déclenché à la demande depuis le dashboard (bouton "Sonder ce prix" sur une
ligne gagnante), un listing×marché à la fois -> fenêtre d'exposition de
quelques secondes, jamais de sonde en masse automatique.

Méthode :
  1. baisse le prix de PROBE_DROP_PCT (repasse probablement perdant)
  2. lit le vrai price_to_win révélé
  3. remonte à price_to_win + marge de sécurité (regagne la BackBox, au prix
     réel minimum au lieu de l'ancien prix gonflé)
  4. si le prix sondé gagne encore (le vrai seuil est encore plus bas),
     restaure le prix d'origine sans rien changer (pas de sonde plus
     agressive dans cette version)

Usage:
    export BM_API_KEY="..."
    LISTING_ID=... MARKET=FR SKU=RIP17PM256GA python3 probe_winning_floor.py
"""
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

HOST = "www.backmarket.fr"
PROBE_DROP_PCT = 0.20
SAFETY_MARGIN_PCT = 0.005
SAFETY_MARGIN_MIN_EUR = 0.50
PARIS = ZoneInfo("Europe/Paris")
HERE = Path(__file__).parent
RESULTS_PATH = HERE / "probe_results.json"


def request(url, api_key, method="GET", body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Basic {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "curl/8.7.1",
        },
    )
    with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as resp:
        raw = resp.read()
        return json.loads(raw.decode("utf-8")) if raw else None


def get_competitors(listing_id, market, api_key):
    data = request(f"https://{HOST}/ws/buyback/v1/competitors/{listing_id}", api_key)
    for e in data:
        if e["market"] == market:
            return float(e["price"]["amount"]), float(e["price_to_win"]["amount"]), e["is_winning"]
    raise RuntimeError(f"Marché {market} absent de la réponse competitors pour {listing_id}")


def set_price(listing_id, market, amount, api_key):
    body = {"prices": {market: {"amount": f"{amount:.2f}", "currency": "EUR"}}}
    request(f"https://{HOST}/ws/buyback/v1/listings/{listing_id}", api_key, method="PUT", body=body)


def append_result(record):
    history = []
    if RESULTS_PATH.exists():
        history = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    history.append(record)
    RESULTS_PATH.write_text(json.dumps(history, ensure_ascii=False), encoding="utf-8")


def main():
    api_key = os.environ.get("BM_API_KEY")
    listing_id = os.environ.get("LISTING_ID")
    market = os.environ.get("MARKET")
    sku = os.environ.get("SKU", "")
    if not api_key or not listing_id or not market:
        print("Erreur: BM_API_KEY, LISTING_ID et MARKET sont requis.", file=sys.stderr)
        sys.exit(1)

    ts = datetime.now(PARIS).isoformat(timespec="seconds")
    record = {"ts": ts, "listing_id": listing_id, "market": market, "sku": sku}

    print(f"=== {sku} / {market} ===")
    original, ptw, winning = get_competitors(listing_id, market, api_key)
    record["original_price"] = original
    print(f"  Prix actuel: {original:.2f}€, is_winning={winning}")

    if not winning:
        print("  Déjà perdant -> price_to_win est déjà fiable, rien à sonder.")
        record["status"] = "not_winning_already_reliable"
        record["price_to_win"] = ptw
        append_result(record)
        return

    probe_price = round(original * (1 - PROBE_DROP_PCT), 2)
    print(f"  Sonde: {probe_price:.2f}€")
    set_price(listing_id, market, probe_price, api_key)
    time.sleep(1.0)

    _, revealed_ptw, still_winning = get_competitors(listing_id, market, api_key)

    if still_winning:
        print(f"  Toujours gagnant à {probe_price:.2f}€ -> vrai seuil encore plus bas, restauration de {original:.2f}€.")
        set_price(listing_id, market, original, api_key)
        record["status"] = "floor_below_probe"
        record["probe_price"] = probe_price
    else:
        margin = max(revealed_ptw * SAFETY_MARGIN_PCT, SAFETY_MARGIN_MIN_EUR)
        optimized = round(revealed_ptw + margin, 2)
        print(f"  Vrai seuil révélé: {revealed_ptw:.2f}€ -> nouveau prix {optimized:.2f}€ (marge {margin:.2f}€)")
        set_price(listing_id, market, optimized, api_key)
        time.sleep(1.0)
        _, final_ptw, final_winning = get_competitors(listing_id, market, api_key)
        if final_winning:
            savings = round(original - optimized, 2)
            print(f"  Confirmé gagnant à {optimized:.2f}€. Économie: {savings:.2f}€.")
            record["status"] = "optimized"
            record["revealed_threshold"] = revealed_ptw
            record["new_price"] = optimized
            record["savings"] = savings
        else:
            print(f"  ATTENTION: pas gagnant au prix optimisé ({optimized:.2f}€) -> restauration de {original:.2f}€.")
            set_price(listing_id, market, original, api_key)
            record["status"] = "optimize_failed_reverted"
            record["revealed_threshold"] = revealed_ptw

    append_result(record)
    print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    main()
