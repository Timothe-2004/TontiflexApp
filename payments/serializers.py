"""
Serializers pour le module Payments KKiaPay
"""
from rest_framework import serializers
from decimal import Decimal
from .models import KKiaPayTransaction


class KKiaPayTransactionSerializer(serializers.ModelSerializer):
    """
    Serializer pour afficher les transactions KKiaPay
    """
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_type_transaction_display', read_only=True)
    is_success = serializers.BooleanField(read_only=True)
    is_pending = serializers.BooleanField(read_only=True)
    user_display = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = KKiaPayTransaction
        fields = [
            'id', 'reference_tontiflex', 'reference_kkiapay', 
            'type_transaction', 'type_display', 'status', 'status_display',
            'montant', 'devise', 'numero_telephone', 'description',
            'user', 'user_display', 'is_success', 'is_pending',
            'created_at', 'updated_at', 'processed_at'
        ]
        read_only_fields = [
            'id', 'reference_tontiflex', 'reference_kkiapay', 'status',
            'created_at', 'updated_at', 'processed_at'
        ]


class PaymentInitiationSerializer(serializers.Serializer):
    """
    Serializer pour initier un paiement KKiaPay
    """
    
    montant = serializers.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        min_value=Decimal('0.01'),
        help_text="Montant à payer en XOF"
    )
    numero_telephone = serializers.CharField(
        max_length=20,
        help_text="Numéro de téléphone Mobile Money (format: +229xxxxxxxx)"
    )
    type_transaction = serializers.ChoiceField(
        choices=KKiaPayTransaction.TYPE_CHOICES,
        help_text="Type de transaction"
    )
    description = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="Description optionnelle de la transaction"
    )
    objet_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID de l'objet concerné (tontine, compte épargne, etc.)"
    )
    objet_type = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        help_text="Type d'objet concerné"
    )
    
    def validate_numero_telephone(self, value):
        """
        Valide le format du numéro de téléphone
        """
        # Supprimer les espaces et caractères spéciaux
        clean_number = ''.join(filter(str.isdigit, value.replace('+', '')))
        
        # Vérification de la longueur (8 à 15 chiffres)
        if len(clean_number) < 8 or len(clean_number) > 15:
            raise serializers.ValidationError(
                "Le numéro de téléphone doit contenir entre 8 et 15 chiffres"
            )
        
        return value


class PaymentStatusSerializer(serializers.Serializer):
    """
    Serializer pour vérifier le statut d'une transaction
    """
    
    reference_tontiflex = serializers.CharField(
        max_length=50,
        help_text="Référence TontiFlex de la transaction"
    )


class SandboxTestSerializer(serializers.Serializer):
    """
    Serializer pour les tests en mode SANDBOX
    """
    
    SCENARIO_CHOICES = [
        ('success', 'Test de succès'),
        ('failure', 'Test d\'échec'),
        ('timeout', 'Test de timeout'),
    ]
    
    scenario = serializers.ChoiceField(
        choices=SCENARIO_CHOICES,
        default='success',
        help_text="Scénario de test à simuler"
    )
    montant = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('1000.00'),
        min_value=Decimal('0.01'),
        help_text="Montant de test en XOF"
    )
    
    def validate(self, data):
        """Validation globale pour les tests sandbox"""
        from .config import kkiapay_config
        
        if not kkiapay_config.sandbox:
            raise serializers.ValidationError(
                "Les tests ne sont disponibles qu'en mode SANDBOX"
            )
        
        return data


class GeneratePaymentLinkSerializer(serializers.Serializer):
    """
    Serializer pour générer un lien de paiement KKiaPay
    """
    
    montant = serializers.DecimalField(
        max_digits=15, 
        decimal_places=2,
        min_value=Decimal('0.01'),
        help_text="Montant à payer en XOF"
    )
    numero_telephone = serializers.CharField(
        max_length=20,
        help_text="Numéro de téléphone Mobile Money (format: +229xxxxxxxx)"
    )
    type_transaction = serializers.ChoiceField(
        choices=KKiaPayTransaction.TYPE_CHOICES,
        help_text="Type de transaction"
    )
    description = serializers.CharField(
        max_length=200, 
        required=False,
        allow_blank=True,
        help_text="Description optionnelle de la transaction"
    )
    objet_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID de l'objet concerné (tontine, compte épargne, etc.)"
    )
    objet_type = serializers.CharField(
        max_length=50, 
        required=False,
        allow_blank=True,
        help_text="Type d'objet concerné"
    )
    metadata = serializers.JSONField(
        required=False,
        help_text="Métadonnées additionnelles"
    )
    callback_url = serializers.URLField(
        required=False, 
        allow_blank=True, 
        allow_null=True,
        help_text="URL de retour après paiement"
    )
    
    def validate_numero_telephone(self, value):
        """
        Valide le format du numéro de téléphone
        """
        # Supprimer les espaces et caractères spéciaux
        clean_number = ''.join(filter(str.isdigit, value.replace('+', '')))
        
        # Vérification de la longueur (8 à 15 chiffres)
        if len(clean_number) < 8 or len(clean_number) > 15:
            raise serializers.ValidationError(
                "Le numéro de téléphone doit contenir entre 8 et 15 chiffres"
            )
        
        return value
