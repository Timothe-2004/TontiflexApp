"""
Serializers Django REST Framework pour le module Notifications.
"""
from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer pour les notifications"""
    utilisateur_nom = serializers.CharField(source='utilisateur.username', read_only=True)
    objet_lie_nom = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'utilisateur', 'utilisateur_nom', 'titre', 'message',
            'canal', 'envoye', 'date_creation', 'date_envoi',
            'content_type', 'object_id', 'objet_lie_nom',
            'donnees_supplementaires', 'actions'
        ]
        read_only_fields = ['id', 'date_creation', 'date_envoi']
    
    def get_objet_lie_nom(self, obj):
        """Retourne une représentation string de l'objet lié"""
        if obj.objet_lie:
            return str(obj.objet_lie)
        return None


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création de notifications"""
    
    class Meta:
        model = Notification
        fields = [
            'utilisateur', 'titre', 'message', 'canal',
            'content_type', 'object_id', 'donnees_supplementaires', 'actions'
        ]
