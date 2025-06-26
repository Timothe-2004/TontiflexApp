"""
Serializers Django REST Framework pour le module Mobile Money.
Gère les transactions et opérateurs Mobile Money.
"""
from rest_framework import serializers
from .models import TransactionMobileMoney, OperateurMobileMoney


class OperateurMobileMoneySerializer(serializers.ModelSerializer):
    """Serializer pour les opérateurs Mobile Money"""
    
    class Meta:
        model = OperateurMobileMoney
        fields = '__all__'


class TransactionMobileMoneySerializer(serializers.ModelSerializer):
    """Serializer pour les transactions Mobile Money"""
    operateur_nom = serializers.CharField(source='operateur.nom', read_only=True)
    client_nom = serializers.CharField(source='client.nom_complet', read_only=True)
    
    class Meta:
        model = TransactionMobileMoney
        fields = '__all__'


class TransactionDetailSerializer(TransactionMobileMoneySerializer):
    """Serializer détaillé pour les transactions avec métadonnées"""
    
    class Meta(TransactionMobileMoneySerializer.Meta):
        fields = '__all__'
