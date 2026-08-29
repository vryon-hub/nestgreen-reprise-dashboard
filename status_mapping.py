"""
Regroupement des statuts de commande BuyBack (/ws/buyback/v1/orders) en 3 catégories
pour calculer un taux de transformation "promesse -> reprise effective".
"""

STATUS_GROUP = {
    'PAID': 'success',
    'MONEY_TRANSFERED': 'success',
    'VALIDATED': 'success',
    'CANCELED': 'lost',
    'SUSPENDED': 'lost',
    'NEW': 'in_progress',
    'PENDING': 'in_progress',
    'TO_SEND': 'in_progress',
    'SENT': 'in_progress',
    'RECEIVED': 'in_progress',
    'COUNTER_PROPOSAL': 'in_progress',
}
STATUS_GROUP_ORDER = ['success', 'lost', 'in_progress']
STATUS_GROUP_LABEL = {
    'success': 'Finalisée (payée)',
    'lost': 'Perdue (annulée/suspendue)',
    'in_progress': 'En cours',
}
# ordre d'affichage détaillé, du plus "réussi" au moins avancé
STATUS_ORDER = [
    'MONEY_TRANSFERED', 'PAID', 'RECEIVED', 'VALIDATED', 'COUNTER_PROPOSAL',
    'SENT', 'TO_SEND', 'PENDING', 'NEW', 'SUSPENDED', 'CANCELED',
]
STATUS_LABEL = {
    'MONEY_TRANSFERED': 'Argent transféré',
    'PAID': 'Payée',
    'RECEIVED': 'Reçue',
    'VALIDATED': 'Validée',
    'COUNTER_PROPOSAL': 'Contre-proposition',
    'SENT': 'Expédiée (client)',
    'TO_SEND': 'À expédier (client)',
    'PENDING': 'En attente',
    'NEW': 'Nouvelle',
    'SUSPENDED': 'Suspendue',
    'CANCELED': 'Annulée',
}
