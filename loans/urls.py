"""
ROUTES API POUR LE MODULE PRÊTS - TONTIFLEX

Définition de toutes les routes REST pour:
1. Demandes de prêt (CRUD + workflow)
2. Conditions de remboursement
3. Prêts accordés et décaissements
4. Échéances et remboursements
5. Paiements Mobile Money
6. Rapports et statistiques

Organisation claire des endpoints par entité
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LoanApplicationViewSet, LoanTermsViewSet, LoanViewSet,
    RepaymentScheduleViewSet, PaymentViewSet, LoanReportViewSet
)

app_name = 'loans'

# Configuration du routeur pour les ViewSets
router = DefaultRouter()

# Routes principales des prêts
router.register(r'applications', LoanApplicationViewSet, basename='application')
router.register(r'terms', LoanTermsViewSet, basename='terms')
router.register(r'loans', LoanViewSet, basename='loan')
router.register(r'schedules', RepaymentScheduleViewSet, basename='schedule')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'reports', LoanReportViewSet, basename='report')

urlpatterns = [
    # Routes générées automatiquement par le routeur
    path('', include(router.urls)),
    
    # Routes personnalisées additionnelles si nécessaire
    # Elles seront ajoutées ici au besoin
]

"""
DOCUMENTATION DES ENDPOINTS DISPONIBLES:

=== DEMANDES DE PRÊT (/loans/applications/) ===
GET    /                      - Liste des demandes (filtré par rôle)
POST   /                      - Créer une nouvelle demande (Client)
GET    /{id}/                 - Détail d'une demande
PUT    /{id}/                 - Modifier une demande (si statut permet)
DELETE /{id}/                 - Supprimer une demande (si statut permet)

POST   /{id}/process_application/  - Traiter demande (Superviseur SFD)
POST   /{id}/admin_decision/       - Validation finale (Admin SFD)
GET    /{id}/rapport_analyse/      - Rapport d'analyse détaillé

=== CONDITIONS DE REMBOURSEMENT (/loans/terms/) ===
GET    /                      - Liste des conditions
POST   /                      - Créer des conditions (Superviseur SFD)
GET    /{id}/                 - Détail des conditions
PUT    /{id}/                 - Modifier des conditions
DELETE /{id}/                 - Supprimer des conditions

GET    /simuler_amortissement/ - Simuler tableau d'amortissement

=== PRÊTS ACCORDÉS (/loans/loans/) ===
GET    /                      - Liste des prêts (filtré par rôle)
GET    /{id}/                 - Détail d'un prêt
PUT    /{id}/                 - Modifier un prêt (si autorisé)

POST   /{id}/decaissement/     - Marquer comme décaissé (Agent/Admin)
GET    /{id}/calendrier_remboursement/ - Calendrier complet

=== ÉCHÉANCES (/loans/schedules/) ===
GET    /                      - Liste des échéances (filtré par rôle)
GET    /{id}/                 - Détail d'une échéance

GET    /a_venir/              - Échéances à venir (paramètre ?jours=30)
GET    /en_retard/            - Échéances en retard

=== PAIEMENTS (/loans/payments/) ===
GET    /                      - Liste des paiements (filtré par rôle)
POST   /                      - Initier un paiement Mobile Money
GET    /{id}/                 - Détail d'un paiement

POST   /{id}/confirmer/       - Confirmer manuellement (Agent/Admin)

=== RAPPORTS (/loans/reports/) ===
GET    /statistiques/         - Statistiques générales (?periode_mois=12)
GET    /tableau_bord/         - Dashboard adapté au rôle
GET    /export/               - Export données (?format=csv|excel)

=== PARAMÈTRES COMMUNS ===
- Tous les endpoints supportent la pagination
- Filtrage automatique par SFD selon le rôle
- Permissions strictes par type d'utilisateur
- Réponses JSON standardisées avec gestion d'erreurs

=== CODES DE RETOUR ===
200 - Succès
201 - Créé avec succès
400 - Erreur de validation
401 - Non authentifié
403 - Non autorisé
404 - Non trouvé
500 - Erreur serveur

=== AUTHENTIFICATION ===
Toutes les routes nécessitent une authentification.
Utiliser le header: Authorization: Bearer <token>

=== EXEMPLES D'UTILISATION ===

# Créer une demande de prêt (Client)
POST /loans/applications/
{
    "montant_souhaite": 500000,
    "duree_pret": 12,
    "type_pret": "consommation",
    "objet_pret": "Achat matériel professionnel",
    "revenus_mensuel": 150000,
    "charges_mensuelles": 80000,
    "documents_justificatifs": <file_upload>
}

# Traiter une demande (Superviseur SFD)
POST /loans/applications/{id}/process_application/
{
    "action": "approuver",
    "montant_accorde": 450000,
    "taux_interet": 15.0,
    "duree_mois": 12,
    "commentaire": "Dossier complet, profil favorable"
}

# Validation finale (Admin SFD)
POST /loans/applications/{id}/admin_decision/
{
    "action": "valider",
    "commentaire": "Prêt accordé selon conditions superviseur"
}

# Décaissement (Agent/Admin)
POST /loans/loans/{id}/decaissement/
{
    "date_decaissement": "2024-01-15",
    "mode_decaissement": "especes",
    "commentaire": "Décaissement en agence principale"
}

# Paiement Mobile Money (Client)
POST /loans/payments/
{
    "echeance": 123,
    "montant": 45000,
    "numero_telephone": "22890123456"
}

# Simulation amortissement
GET /loans/terms/simuler_amortissement/?montant=500000&taux=15&duree=12

# Statistiques (Admin)
GET /loans/reports/statistiques/?periode_mois=6

# Dashboard
GET /loans/reports/tableau_bord/
"""
