"""
TEMPORAIREMENT DÉSACTIVÉ - MIGRATION VERS KKIAPAY
Ce module sera supprimé une fois la migration KKiaPay terminée.

Nouveau module payments/ avec KKiaPay intégré.
Documentation : https://kkiapay.me/kkiapay-integration/?lang=en
Dashboard : https://app.kkiapay.me/dashboard

Mode SANDBOX activé pour tests et validation.
Changement vers LIVE après validation complète.

VOIR PROJET_HISTORIQUE.md pour suivi détaillé de la migration.
"""

"""
Views Django REST Framework pour le module Mobile Money.
"""
from rest_framework import viewsets, permissions
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample, OpenApiResponse

from .models import TransactionMobileMoney, OperateurMobileMoney
from .serializers import (
    TransactionMobileMoneySerializer,
    TransactionDetailSerializer,
    OperateurMobileMoneySerializer
)


@extend_schema_view(
    list=extend_schema(
        summary="Historique des transactions Mobile Money",
        description="""
        Affiche l'historique des transactions Mobile Money de la plateforme TontiFlex.
        
        Types de transactions TontiFlex:
        Paiement adhésion: Frais d'entrée dans une tontine
        Cotisation: Versement quotidien dans la tontine
        Commission SFD: 1ère cotisation de chaque cycle
        Retrait: Retrait de fonds par un participant
        Remboursement: Annulation ou retour de fonds
        
        Opérateurs supportés:
        MTN Mobile Money (Bénin, Burkina, Côte d'Ivoire)
        Moov Money (réseau Orange/Moov)
        
        Statuts de transaction:
        en_cours: Transaction initiée, en attente confirmation
        confirmee: Paiement confirmé par l'opérateur
        echouee: Transaction échouée (solde insuffisant, erreur technique)
        annulee: Transaction annulée par l'utilisateur
        remboursee: Fonds restitués au client
        
        Filtres disponibles:
        Par période (date début/fin)
        Par type de transaction
        Par statut
        Par opérateur Mobile Money
        Par numéro de téléphone
        """,
        responses={200: TransactionMobileMoneySerializer(many=True)}
    ),
    retrieve=extend_schema(
        summary="Détails d'une transaction Mobile Money",
        description="""
        Récupère les détails complets d'une transaction Mobile Money.
        
        Informations détaillées:
        Références de transaction (TontiFlex + Opérateur)
        Timestamps complets (initiation, confirmation, finalisation)
        Détails du compte Mobile Money utilisé
        Frais appliqués (opérateur + commission TontiFlex)
        Contexte de la transaction (tontine, participant concerné)
        Messages d'erreur éventuels
        Historique des tentatives
        
        Traçabilité complète:
        ID de transaction chez l'opérateur
        Codes de retour et messages système
        Journal des statuts successifs
        Liens vers les entités TontiFlex concernées
        
        Permissions requises:
        Utilisateur concerné par la transaction
        Staff SFD pour les transactions de leur SFD
        Admin plateforme pour toutes les transactions
        """,
        responses={
            200: TransactionDetailSerializer,
            403: OpenApiResponse(description="Accès refusé - transaction non accessible"),
            404: OpenApiResponse(description="Transaction introuvable")
        }
    )
)
@extend_schema(tags=["💳 Mobile Money"])
class TransactionMobileMoneyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour la consultation des transactions Mobile Money
    """
    queryset = TransactionMobileMoney.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TransactionDetailSerializer
        return TransactionMobileMoneySerializer
    
    def get_queryset(self):
        """Filter transactions based on user permissions"""
        user = self.request.user
        
        if hasattr(user, 'adminplateforme'):
            # Admin plateforme peut voir toutes les transactions
            return TransactionMobileMoney.objects.all()
        elif hasattr(user, 'agentsfd') or hasattr(user, 'superviseurssfd') or hasattr(user, 'administrateurssfd'):
            # Staff SFD peut voir les transactions de leur SFD
            sfd = getattr(user.agentsfd, 'sfd', None) or getattr(user.superviseurssfd, 'sfd', None) or getattr(user.administrateurssfd, 'sfd', None)
            if sfd:
                # Transactions liées aux adhésions et cotisations de ce SFD
                from tontines.models import Adhesion, Cotisation
                transaction_ids = set()
                
                # Transactions d'adhésions
                adhesions = Adhesion.objects.filter(tontine__administrateurId__sfd=sfd)
                transaction_ids.update(adhesions.values_list('transaction_paiement_id', flat=True))
                
                # Transactions de cotisations
                cotisations = Cotisation.objects.filter(tontine__administrateurId__sfd=sfd)
                transaction_ids.update(cotisations.values_list('transaction_mobile_money_id', flat=True))
                
                return TransactionMobileMoney.objects.filter(id__in=transaction_ids)
        elif hasattr(user, 'clientsfd'):
            # Client peut voir ses propres transactions
            from tontines.models import Adhesion, Cotisation
            transaction_ids = set()
            
            # Transactions d'adhésions du client
            adhesions = Adhesion.objects.filter(client=user.clientsfd)
            transaction_ids.update(adhesions.values_list('transaction_paiement_id', flat=True))
              # Transactions de cotisations du client
            cotisations = Cotisation.objects.filter(client=user.clientsfd)
            transaction_ids.update(cotisations.values_list('transaction_mobile_money_id', flat=True))
            
            return TransactionMobileMoney.objects.filter(id__in=transaction_ids)
        
        return TransactionMobileMoney.objects.none()


@extend_schema_view(
    list=extend_schema(
        summary="Liste des opérateurs Mobile Money",
        description="""
        Affiche la liste des opérateurs Mobile Money supportés par TontiFlex.
        
        **Opérateurs actuellement supportés**:
        
        🇧🇯 **Bénin**:
        - MTN Mobile Money (réseau MTN Benin)
        - Moov Money (réseau Moov Africa Benin)
        
        🇧🇫 **Burkina Faso**:
        - MTN Mobile Money (réseau MTN Burkina)
        - Orange Money (réseau Orange Burkina)
          🇨🇮 Côte d'Ivoire:
        MTN Mobile Money (réseau MTN CI)
        Orange Money (réseau Orange CI)
        Wave (portefeuille mobile)
        
        Informations par opérateur:
        Nom commercial et code technique
        Pays de couverture et préfixes supportés
        Frais de transaction par tranche
        Limites de transaction (min/max)
        Statut de disponibilité (actif/maintenance)
        API endpoints et versions supportées
        
        Intégration technique:
        API REST pour initiation de paiement
        Webhooks pour confirmation de transaction
        Format de réponse standardisé
        Gestion des codes d'erreur spécifiques
        """,
        responses={200: OperateurMobileMoneySerializer(many=True)}
    ),
    retrieve=extend_schema(
        summary="Détails d'un opérateur Mobile Money",
        description="""
        Récupère les informations détaillées d'un opérateur Mobile Money.
        
        Informations techniques:
        Configuration API (endpoints, headers, authentification)
        Grille tarifaire complète par type de transaction
        Codes d'erreur et messages spécifiques
        Limites opérationnelles (montants, fréquence)
        Horaires de disponibilité et maintenance
        
        Statistiques d'utilisation:
        Volume de transactions traité
        Taux de succès et d'échec
        Temps de réponse moyen
        Dernière synchronisation avec l'API
        
        Utilisé pour:
        Configuration des services de paiement
        Diagnostic des problèmes de transaction
        Optimisation des routes de paiement
        Reporting et analytics
        """,
        responses={
            200: OperateurMobileMoneySerializer,
            404: OpenApiResponse(description="Opérateur introuvable")
        }
    )
)
@extend_schema(tags=["📱 Opérateurs Mobile Money"])
class OperateurMobileMoneyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour la consultation des opérateurs Mobile Money
    """
    queryset = OperateurMobileMoney.objects.all()
    serializer_class = OperateurMobileMoneySerializer
    permission_classes = [permissions.IsAuthenticated]
