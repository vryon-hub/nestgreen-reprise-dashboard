"""
Correspondance entre le grade "commande" (API /ws/buyback/v1/orders, listing.grade)
et le libellé officiel BackMarket "annonce" (API /ws/buyback/v1/listings, aestheticGradeCode),
vérifiée empiriquement par croisement du SKU sur >100 commandes (2026-08-26) :
chaque suffixe de SKU (GA-GF) correspond systématiquement à un seul grade commande, sans
mélange. Voir buyback_backmarket_project.md pour le détail de la vérification.
"""

# ordre du meilleur au pire état, identique à celui utilisé côté onglet Prix (GRADE_ORDER)
ORDER_GRADE_TO_LABEL = {
    'DIAMOND':  'Fonctionnel - Parfait état',
    'PLATINUM': 'Fonctionnel - Très bon état',
    'GOLD':     'Fonctionnel - État correct',
    'SILVER':   'Fonctionnel - Cassé',
    'BRONZE':   'Non fonctionnel - État correct',
    'STALLONE': 'Non fonctionnel - Cassé',
}
GRADE_LABEL_ORDER = [
    'Fonctionnel - Parfait état',
    'Fonctionnel - Très bon état',
    'Fonctionnel - État correct',
    'Fonctionnel - Cassé',
    'Non fonctionnel - État correct',
    'Non fonctionnel - Cassé',
]
