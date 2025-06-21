
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

User = get_user_model()


class Notification(models.Model):
    """
    Modèle simplifié pour les notifications du système.
    """
    
    CANAL_CHOICES = [
        ('app', 'Application'),
        ('email', 'Email'),
    ]
    
    # Champs principaux
    utilisateur = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="Utilisateur"
    )
    titre = models.CharField(max_length=200, verbose_name="Titre")
    message = models.TextField(verbose_name="Message")
    
    # Dates
    date_creation = models.DateTimeField(
        default=timezone.now,
        verbose_name="Date de création"
    )
    
    # Canal et métadonnées
    canal = models.CharField(
        max_length=10,
        choices=CANAL_CHOICES,
        default='app',
        verbose_name="Canal"
    )
    envoye = models.BooleanField(default=False, verbose_name="Envoyé")
    date_envoi = models.DateTimeField(null=True, blank=True, verbose_name="Date d'envoi")
    
    # Relation générique vers n'importe quel objet
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    objet_lie = GenericForeignKey('content_type', 'object_id')
    
    # Données supplémentaires JSON
    donnees_supplementaires = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Données supplémentaires"
    )
    
    # Actions disponibles (boutons dans l'interface)
    actions = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Actions",
        help_text="Liste des actions disponibles sous forme de boutons"
    )
    
    class Meta:
        db_table = 'core_notification'
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['utilisateur', 'date_creation']),
            models.Index(fields=['canal']),
        ]
    
    def __str__(self):
        return f"{self.titre} - {self.utilisateur.username}"
    
    @classmethod
    def get_recentes(cls, utilisateur, limit=10):
        """Retourne les notifications récentes pour un utilisateur."""
        return cls.objects.filter(
            utilisateur=utilisateur
        ).order_by('-date_creation')[:limit]