#!/usr/bin/env python3
"""
Extrait toutes les BuyBack listings (prix de reprise) du compte marchand BackMarket
via GET /ws/buyback/v1/listings, en suivant la pagination par cursor.

Usage:
    export BM_API_KEY="<clé base64 user:token, avec padding ==>"
    python3 extract_buyback_listings.py [--out-dir .] [--host www.backmarket.fr]
"""

import argparse
import csv
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

DEFAULT_HOST = "www.backmarket.fr"
PAGE_SIZE = 100
MAX_RETRIES = 3


def fetch_page(url, api_key):
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {api_key}",
            "Accept": "application/json",
            # Cloudflare bloque la signature TLS/UA par défaut d'urllib (Error 1010) ;
            # curl passe, donc on emprunte son User-Agent.
            "User-Agent": "curl/8.7.1",
        },
    )
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code in (429, 500, 502, 503) and attempt < MAX_RETRIES:
                time.sleep(2 * attempt)
                continue
            print(f"Erreur HTTP {e.code} sur {url}: {body}", file=sys.stderr)
            raise
    raise RuntimeError("unreachable")


def fetch_all_listings(api_key, host):
    url = f"https://{host}/ws/buyback/v1/listings?pageSize={PAGE_SIZE}"
    results = []
    page = 0
    while url:
        page += 1
        data = fetch_page(url, api_key)
        results.extend(data["results"])
        print(f"  page {page}: +{len(data['results'])} listings (total {len(results)})", file=sys.stderr)
        url = data.get("next")
    return results


def write_csv_long(listings, path):
    """Une ligne par (listing, marché) — format tidy pour analyse/pivot."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["listing_id", "product_id", "sku", "aesthetic_grade", "market", "price_amount", "currency"])
        for listing in listings:
            for market, price in listing["prices"].items():
                w.writerow([
                    listing["id"],
                    listing["productId"],
                    listing["sku"] or "",
                    listing["aestheticGradeCode"],
                    market,
                    price["amount"],
                    price["currency"],
                ])


def write_json(listings, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=".", help="Dossier de sortie (défaut: dossier courant)")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host API (défaut: {DEFAULT_HOST})")
    args = parser.parse_args()

    api_key = os.environ.get("BM_API_KEY")
    if not api_key:
        print("Erreur: variable d'environnement BM_API_KEY manquante.", file=sys.stderr)
        print('  export BM_API_KEY="<clé base64 user:token>"', file=sys.stderr)
        sys.exit(1)

    print(f"Extraction des BuyBack listings depuis {args.host} ...", file=sys.stderr)
    listings = fetch_all_listings(api_key, args.host)
    print(f"Total: {len(listings)} listings récupérées.", file=sys.stderr)

    os.makedirs(args.out_dir, exist_ok=True)
    csv_path = os.path.join(args.out_dir, "buyback_listings.csv")
    json_path = os.path.join(args.out_dir, "buyback_listings.json")
    write_csv_long(listings, csv_path)
    write_json(listings, json_path)
    print(f"Écrit: {csv_path}", file=sys.stderr)
    print(f"Écrit: {json_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
