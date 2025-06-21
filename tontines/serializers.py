"""
Serializers Django REST Framework pour TontiFlex.
Gère tous les modèles avec actions personnalisées selon copilot-instructions.md.
"""
from rest_framework import serializers
from decimal import Decimal

# Import des modèles TontiFlex
from .models import (
    Adhesion, Tontine, TontineParticipant, Cotisation, Retrait, 
    SoldeTontine, CarnetCotisation
)
from accounts.models import Client, SFD, AgentSFD, SuperviseurSFD, AdministrateurSFD, AdminPlateforme
from mobile_money.models import TransactionMobileMoney, OperateurMobileMoney
from notifications.models import Notification


# ============================================================================
# SERIALIZERS TONTINES (existants + nouveaux)
# ============================================================================

class AdhesionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Adhesion
        fields = '__all__'


class TontineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tontine
        fields = '__all__'


class TontineParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = TontineParticipant
        fields = '__all__'


class CotisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cotisation
        fields = '__all__'


class RetraitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Retrait
        fields = '__all__'


class SoldeTontineSerializer(serializers.ModelSerializer):
    """Serializer pour le nouveau modèle SoldeTontine."""
    class Meta:
        model = SoldeTontine
        fields = '__all__'


class CarnetCotisationSerializer(serializers.ModelSerializer):
    """Serializer pour le nouveau modèle CarnetCotisation."""
    class Meta:
        model = CarnetCotisation
        fields = '__all__'


# ============================================================================
# SERIALIZERS ACCOUNTS
# ============================================================================

class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = '__all__'


class SFDSerializer(serializers.ModelSerializer):
    class Meta:
        model = SFD
        fields = '__all__'


class AgentSFDSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentSFD
        fields = '__all__'


class SuperviseurSFDSerializer(serializers.ModelSerializer):
    class Meta:
        model = SuperviseurSFD
        fields = '__all__'


class AdministrateurSFDSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdministrateurSFD
        fields = '__all__'


class AdminPlateformeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminPlateforme
        fields = '__all__'


# ============================================================================
# SERIALIZERS MOBILE MONEY
# ============================================================================

class OperateurMobileMoneySerializer(serializers.ModelSerializer):
    class Meta:
        model = OperateurMobileMoney
        fields = '__all__'


class TransactionMobileMoneySerializer(serializers.ModelSerializer):
    """Serializer pour TransactionMobileMoney avec nouveau champ is_commission."""
    class Meta:
        model = TransactionMobileMoney
        fields = '__all__'


# ============================================================================
# SERIALIZERS NOTIFICATIONS
# ============================================================================

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'


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
    numero_mobile_money = serializers.CharField(
        max_length=15,
        help_text="Numéro de téléphone Mobile Money du client"
    )
    operateur = serializers.ChoiceField(
        choices=[('mtn', 'MTN'), ('moov', 'Moov'), ('orange', 'Orange')],
        default='mtn',
        help_text="Opérateur Mobile Money"
    )


class IntegrerRequestSerializer(serializers.Serializer):
    """Serializer pour l'action integrer sur AdhesionViewSet."""
    # Pas de champs requis - l'intégration se fait automatiquement
    pass


class CotiserRequestSerializer(serializers.Serializer):
    """Serializer pour l'action cotiser sur WorkflowAdhesionViewSet (Adhesion)."""
    client_id = serializers.UUIDField(
        help_text="ID du client qui cotise"
    )
    nombre_mises = serializers.IntegerField(
        min_value=1,
        max_value=62,  # Maximum 2 cycles complets
        help_text="Nombre de mises à payer (1-62)"
    )
    numero_mobile_money = serializers.CharField(
        max_length=15,
        help_text="Numéro de téléphone Mobile Money pour le paiement"
    )
    operateur = serializers.ChoiceField(
        choices=[('mtn', 'MTN'), ('moov', 'Moov'), ('orange', 'Orange')],
        default='mtn',
        help_text="Opérateur Mobile Money"
    )
