"""
Serializers Django REST Framework pour le module Savings.
Gère uniquement les modèles relatifs aux comptes épargne et transactions.
"""
from rest_framework import serializers
from decimal import Decimal

# Import des modèles Savings
from .models import SavingsAccount, SavingsTransaction


# ============================================================================
# SERIALIZERS PRINCIPAUX
# ============================================================================

class SavingsAccountSerializer(serializers.ModelSerializer):
    """Serializer pour les comptes épargne"""
    client_nom = serializers.CharField(source='client.nom_complet', read_only=True)
    agent_nom = serializers.CharField(source='agent_validateur.nom_complet', read_only=True)
    sfd_nom = serializers.CharField(source='nom_sfd', read_only=True)
    solde_disponible = serializers.SerializerMethodField()
    prochaine_action = serializers.CharField(source='prochaine_action_requise', read_only=True)
    
    class Meta:
        model = SavingsAccount
        fields = '__all__'
    
    def get_solde_disponible(self, obj):
        """Calcule le solde disponible du compte"""
        return obj.calculer_solde()


class SavingsTransactionSerializer(serializers.ModelSerializer):
    """Serializer pour les transactions épargne"""
    client_nom = serializers.CharField(source='compte_epargne.client.nom_complet', read_only=True)
    compte_id = serializers.CharField(source='compte_epargne.id', read_only=True)
    transaction_mm_statut = serializers.CharField(source='transaction_mobile_money.statut', read_only=True)
    
    class Meta:
        model = SavingsTransaction
        fields = '__all__'


# ============================================================================
# SERIALIZERS POUR ACTIONS PERSONNALISÉES
# ============================================================================

class CreateRequestSerializer(serializers.Serializer):
    """Serializer pour l'action create_request."""
    piece_identite = serializers.FileField(
        help_text="Copie numérique de la pièce d'identité (PDF, JPG, PNG)"
    )
    photo_identite = serializers.FileField(
        help_text="Photo d'identité du client (JPG, PNG)"
    )
    numero_telephone_paiement = serializers.CharField(
        max_length=15,
        required=False,
        help_text="Numéro de téléphone Mobile Money pour frais de création"
    )
    operateur_mobile_money = serializers.ChoiceField(
        choices=SavingsAccount.OperateurChoices.choices,
        required=False,
        help_text="Opérateur Mobile Money préféré"
    )


class ValidateRequestSerializer(serializers.Serializer):
    """Serializer pour l'action validate_request par Agent SFD."""
    approuver = serializers.BooleanField(
        help_text="True pour approuver, False pour rejeter"
    )
    commentaires = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        help_text="Commentaires de l'agent lors de la validation"
    )
    raison_rejet = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text="Raison du rejet si non approuvé"
    )
    
    def validate(self, data):
        """Validation croisée des champs"""
        if not data.get('approuver') and not data.get('raison_rejet'):
            raise serializers.ValidationError(
                "La raison du rejet est obligatoire si la demande n'est pas approuvée."
            )
        return data


class PayFeesSerializer(serializers.Serializer):
    """Serializer pour le paiement des frais de création."""
    numero_mobile_money = serializers.CharField(
        max_length=15,
        help_text="Numéro de téléphone Mobile Money"
    )
    operateur = serializers.ChoiceField(
        choices=SavingsAccount.OperateurChoices.choices,
        help_text="Opérateur Mobile Money"
    )
    confirmer_montant = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Confirmation du montant des frais de création"
    )


class DepositSerializer(serializers.Serializer):
    """Serializer pour l'action deposit (dépôt)."""
    montant = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Montant du dépôt en FCFA"
    )
    numero_mobile_money = serializers.CharField(
        max_length=15,
        help_text="Numéro de téléphone Mobile Money"
    )
    operateur = serializers.ChoiceField(
        choices=SavingsAccount.OperateurChoices.choices,
        help_text="Opérateur Mobile Money"
    )
    commentaires = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text="Commentaires optionnels sur le dépôt"
    )
    
    def validate_montant(self, value):
        """Valide le montant minimum pour dépôt"""
        if value < Decimal('100.00'):
            raise serializers.ValidationError(
                "Le montant minimum pour un dépôt est de 100 FCFA."
            )
        return value


class WithdrawSerializer(serializers.Serializer):
    """Serializer pour l'action withdraw (retrait)."""
    montant = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Montant du retrait en FCFA"
    )
    numero_mobile_money = serializers.CharField(
        max_length=15,
        help_text="Numéro de téléphone Mobile Money pour recevoir les fonds"
    )
    operateur = serializers.ChoiceField(
        choices=SavingsAccount.OperateurChoices.choices,
        help_text="Opérateur Mobile Money"
    )
    motif_retrait = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text="Motif du retrait (optionnel)"
    )
    
    def validate_montant(self, value):
        """Valide le montant minimum pour retrait"""
        if value < Decimal('500.00'):
            raise serializers.ValidationError(
                "Le montant minimum pour un retrait est de 500 FCFA."
            )
        return value


# ============================================================================
# SERIALIZERS SPÉCIALISÉS
# ============================================================================

class SavingsAccountSummarySerializer(serializers.ModelSerializer):
    """Serializer simplifié pour la liste des comptes"""
    client_nom = serializers.CharField(source='client.nom_complet', read_only=True)
    solde_disponible = serializers.SerializerMethodField()
    nombre_transactions = serializers.SerializerMethodField()
    derniere_transaction = serializers.SerializerMethodField()
    
    class Meta:
        model = SavingsAccount
        fields = [
            'id', 'client_nom', 'statut', 'date_demande', 'date_activation',
            'solde_disponible', 'nombre_transactions', 'derniere_transaction'
        ]
    
    def get_solde_disponible(self, obj):
        return obj.calculer_solde()
    
    def get_nombre_transactions(self, obj):
        return obj.transactions.filter(
            statut=SavingsTransaction.StatutChoices.CONFIRMEE
        ).count()
    
    def get_derniere_transaction(self, obj):
        derniere = obj.transactions.filter(
            statut=SavingsTransaction.StatutChoices.CONFIRMEE
        ).first()
        return derniere.date_confirmation if derniere else None


class TransactionHistorySerializer(serializers.ModelSerializer):
    """Serializer pour l'historique des transactions"""
    type_display = serializers.CharField(source='get_type_transaction_display', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    
    class Meta:
        model = SavingsTransaction
        fields = [
            'id', 'type_transaction', 'type_display', 'montant', 
            'statut', 'statut_display', 'date_transaction', 
            'date_confirmation', 'operateur', 'commentaires'
        ]


# ============================================================================
# SERIALIZERS DE RÉPONSE
# ============================================================================

class AccountStatusResponseSerializer(serializers.Serializer):
    """Serializer pour les réponses de statut de compte"""
    compte_id = serializers.UUIDField()
    statut = serializers.CharField()
    message = serializers.CharField()
    prochaine_action = serializers.CharField()
    solde_disponible = serializers.DecimalField(max_digits=12, decimal_places=2)


class TransactionResponseSerializer(serializers.Serializer):
    """Serializer pour les réponses de transaction"""
    transaction_id = serializers.UUIDField()
    compte_id = serializers.UUIDField()
    type_transaction = serializers.CharField()
    montant = serializers.DecimalField(max_digits=12, decimal_places=2)
    statut = serializers.CharField()
    message = serializers.CharField()
    reference_mobile_money = serializers.CharField(required=False)
