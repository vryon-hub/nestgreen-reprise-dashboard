#!/usr/bin/env python3
"""
Récupère, pour chaque buyback listing, le statut compétitif par marché via
GET /ws/buyback/v1/competitors/{listingId} : votre prix, le prix pour gagner
la BackBox, et si vous gagnez actuellement.

Rate-limit BackMarket observé (doc) : ~20 requêtes / 10s sur les endpoints
catalog-like. On reste prudent à ~1.5 req/s avec backoff sur 429.

Usage:
    export BM_API_KEY="<clé base64 user:token, avec padding ==>"
    python3 fetch_competitors.py
"""

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

HOST = "www.backmarket.fr"
DELAY = 0.7  # ~1.4 req/s


RETRIABLE_NETWORK_ERRORS = (urllib.error.URLError, ConnectionError, TimeoutError, OSError)


def fetch(url, api_key):
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {api_key}",
            "Accept": "application/json",
            "User-Agent": "curl/8.7.1",
        },
    )
    for attempt in range(1, 6):
        try:
            with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                wait = 3 * attempt
                print(f"  HTTP {e.code}, retry dans {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"Erreur HTTP {e.code} sur {url}: {e.read()}", file=sys.stderr)
            return None
        except RETRIABLE_NETWORK_ERRORS as e:
            wait = 3 * attempt
            print(f"  Erreur réseau ({e}), retry dans {wait}s...", file=sys.stderr)
            time.sleep(wait)
            continue
    return None


def save(result, path="competitors.json"):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    os.replace(tmp, path)


def main():
    api_key = os.environ.get("BM_API_KEY")
    if not api_key:
        print("Erreur: variable d'environnement BM_API_KEY manquante.", file=sys.stderr)
        sys.exit(1)

    listings = json.load(open("buyback_listings.json", encoding="utf-8"))
    try:
        result = json.load(open("competitors.json", encoding="utf-8"))
        print(f"Reprise: {len(result)} listings déjà en cache.", file=sys.stderr)
    except FileNotFoundError:
        result = {}

    errors = []
    total = len(listings)
    todo = [l for l in listings if l["id"] not in result]
    print(f"{len(todo)}/{total} listings à traiter.", file=sys.stderr)

    try:
        for i, listing in enumerate(todo, 1):
            lid = listing["id"]
            data = fetch(f"https://{HOST}/ws/buyback/v1/competitors/{lid}", api_key)
            if data is None:
                errors.append(lid)
            else:
                result[lid] = [
                    {
                        "market": e["market"],
                        "price": float(e["price"]["amount"]),
                        "price_to_win": float(e["price_to_win"]["amount"]),
                        "is_winning": e["is_winning"],
                    }
                    for e in data
                ]
            if i % 25 == 0 or i == len(todo):
                save(result)
                print(f"  {len(result)}/{total} listings traités ({len(errors)} erreurs)", file=sys.stderr)
            time.sleep(DELAY)
    finally:
        save(result)

    print(f"Terminé: {len(result)}/{total} listings résolus, {len(errors)} erreurs.", file=sys.stderr)
    if errors:
        print(f"  IDs en erreur: {errors[:20]}{'...' if len(errors) > 20 else ''}", file=sys.stderr)


if __name__ == "__main__":
    main()
