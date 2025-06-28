"""
Serializers Django REST Framework pour le module Tont    class Meta:
        model = Adhesion
        fields = [
            'id', 'client', 'client_nom', 'tontine', 'tontine_nom',
            'montant_mise', 'numero_telephone_paiement',  # MIGRATION : operateur_mobile_money supprimé
            'document_identite', 'statut_actuel', 'etape_actuelle',
            'date_creation', 'date_validation_agent', 'date_paiement_frais',
            'date_integration', 'frais_adhesion_calcules', 'agent_validateur',
            'agent_nom', 'commentaires_agent', 'raison_rejet', 'prochaine_action'
        ]e uniquement les modèles relatifs aux tontines, adhésions, cotisations, retraits.
"""
from rest_framework import serializers
from decimal import Decimal

# Import des modèles Tontines
from .models import (
    Adhesion, Tontine, TontineParticipant, Cotisation, Retrait, 
    SoldeTontine, CarnetCotisation
)


# ============================================================================
# SERIALIZERS TONTINES
# ============================================================================

class TontineSerializer(serializers.ModelSerializer):
    """Serializer pour les tontines"""
    nombre_participants = serializers.ReadOnlyField()
    
    class Meta:
        model = Tontine
        fields = '__all__'


class TontineParticipantSerializer(serializers.ModelSerializer):
    """Serializer pour les participants aux tontines"""
    client_nom = serializers.CharField(source='client.nom_complet', read_only=True)
    tontine_nom = serializers.CharField(source='tontine.nom', read_only=True)
    solde_disponible = serializers.SerializerMethodField()
    
    class Meta:
        model = TontineParticipant
        fields = '__all__'
    
    def get_solde_disponible(self, obj):
        return obj.calculer_solde_disponible()


class AdhesionSerializer(serializers.ModelSerializer):
    """Serializer pour les demandes d'adhésion"""
    client_nom = serializers.CharField(source='client.nom_complet', read_only=True)
    tontine_nom = serializers.CharField(source='tontine.nom', read_only=True)
    agent_nom = serializers.CharField(source='agent_validateur.nom_complet', read_only=True)
    prochaine_action = serializers.CharField(source='prochaine_action_requise', read_only=True)
    
    class Meta:
        model = Adhesion
        fields = '__all__'


class CotisationSerializer(serializers.ModelSerializer):
    """Serializer pour les cotisations"""
    client_nom = serializers.CharField(source='client.nom_complet', read_only=True)
    tontine_nom = serializers.CharField(source='tontine.nom', read_only=True)
    
    class Meta:
        model = Cotisation
        fields = '__all__'


class RetraitSerializer(serializers.ModelSerializer):
    """Serializer pour les retraits"""
    client_nom = serializers.CharField(source='client.nom_complet', read_only=True)
    tontine_nom = serializers.CharField(source='tontine.nom', read_only=True)
    agent_nom = serializers.CharField(source='agent_validateur.nom_complet', read_only=True)
    
    class Meta:
        model = Retrait
        fields = '__all__'


class SoldeTontineSerializer(serializers.ModelSerializer):
    """Serializer pour les soldes tontine"""
    client_nom = serializers.CharField(source='client.nom_complet', read_only=True)
    tontine_nom = serializers.CharField(source='tontine.nom', read_only=True)
    
    class Meta:
        model = SoldeTontine
        fields = '__all__'


class CarnetCotisationSerializer(serializers.ModelSerializer):
    """Serializer pour les carnets de cotisation"""
    client_nom = serializers.CharField(source='client.nom_complet', read_only=True)
    tontine_nom = serializers.CharField(source='tontine.nom', read_only=True)
    mises_completees = serializers.SerializerMethodField()
    
    class Meta:
        model = CarnetCotisation
        fields = '__all__'
    
    def get_mises_completees(self, obj):
        return sum(obj.mises_cochees) if obj.mises_cochees else 0


# ============================================================================
# SERIALIZERS POUR ACTIONS PERSONNALISÉES
# ============================================================================

class ValiderAgentRequestSerializer(serializers.Serializer):
    """Serializer pour l'action valider_agent sur AdhesionViewSet."""
    commentaires = serializers.CharField(
        max_length=500, 
        required=False, 
        allow_blank=True,
        help_text="Commentaires de l'agent lors de la validation"
    )


class PayerRequestSerializer(serializers.Serializer):
    """Serializer pour l'action payer sur AdhesionViewSet."""
    numero_telephone = serializers.CharField(  # MIGRATION : numero_mobile_money → numero_telephone
        max_length=15,
        help_text="Numéro de téléphone pour le paiement KKiaPay"
    )
    # MIGRATION : operateur supprimé - KKiaPay gère tous les opérateurs automatiquement


class IntegrerRequestSerializer(serializers.Serializer):
    """Serializer pour l'action integrer sur AdhesionViewSet."""
    confirmer = serializers.BooleanField(
        default=True,
        help_text="Confirmer l'intégration du client à la tontine"
    )


class CotiserRequestSerializer(serializers.Serializer):
    """Serializer pour l'action cotiser sur TontineParticipantViewSet."""
    
    montant = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Montant de la cotisation"
    )
    numero_telephone = serializers.CharField(  # MIGRATION : numero_mobile_money → numero_telephone
        max_length=15,
        help_text="Numéro de téléphone pour le paiement KKiaPay"
    )
    # MIGRATION : operateur supprimé - KKiaPay gère tous les opérateurs automatiquement


class IntegrerRequestSerializer(serializers.Serializer):
    """Serializer pour l'action integrer sur AdhesionViewSet."""
    # Pas de champs requis - l'intégration se fait automatiquement
    pass


class AdhesionCotiserRequestSerializer(serializers.Serializer):
    """Serializer pour l'action cotiser sur WorkflowAdhesionViewSet (Adhesion)."""
    client_id = serializers.UUIDField(
        help_text="ID du client qui cotise"
    )
    nombre_mises = serializers.IntegerField(
        min_value=1,
        max_value=62,  # Maximum 2 cycles complets
        help_text="Nombre de mises à payer (1-62)"
    )
    numero_telephone = serializers.CharField(  # MIGRATION : numero_mobile_money → numero_telephone
        max_length=15,
        help_text="Numéro de téléphone pour le paiement KKiaPay"
    )
    # MIGRATION : operateur supprimé - KKiaPay gère tous les opérateurs automatiquement
