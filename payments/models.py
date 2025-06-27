"""
Modèles pour les transactions KKiaPay
====================================

Modèle unifié pour toutes les transactions financières via KKiaPay.
Remplace les multiples modèles Mobile Money par une interface unique.
"""
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal
import uuid

User = get_user_model()


class KKiaPayTransaction(models.Model):
    """
    Modèle unifié pour toutes les transactions KKiaPay
    Remplace les anciens modèles Mobile Money
    """
    
    # Types de transactions TontiFlex
    TYPE_CHOICES = [
        # Tontines
        ('adhesion_tontine', 'Frais d\'adhésion tontine'),
        ('cotisation_tontine', 'Cotisation tontine'),
        ('retrait_tontine', 'Retrait tontine'),
        
        # Épargne
        ('frais_creation_epargne', 'Frais création compte épargne'),
        ('depot_epargne', 'Dépôt épargne'),
        ('retrait_epargne', 'Retrait épargne'),
        
        # Prêts
        ('remboursement_pret', 'Remboursement prêt'),
        
        # Général
        ('autre', 'Autre'),
    ]
    
    # Statuts de transaction
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En cours de traitement'),
        ('success', 'Succès'),
        ('failed', 'Échec'),
        ('cancelled', 'Annulé'),
        ('refunded', 'Remboursé'),
    ]
    
    # Identifiants
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference_tontiflex = models.CharField(
        max_length=50, 
        unique=True,
        help_text="Référence unique TontiFlex"
    )
    reference_kkiapay = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Référence retournée par KKiaPay"
    )
    
    # Informations de base
    type_transaction = models.CharField(max_length=30, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    montant = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    devise = models.CharField(max_length=3, default='XOF')
    
    # Utilisateur et numéro de téléphone
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kkiapay_transactions')
    numero_telephone = models.CharField(
        max_length=20,
        help_text="Numéro Mobile Money du payeur"
    )
    
    # Métadonnées contextuelles
    objet_id = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="ID de l'objet concerné (tontine, compte épargne, prêt, etc.)"
    )
    objet_type = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Type d'objet concerné (Tontine, SavingsAccount, Loan, etc.)"
    )
    description = models.TextField(blank=True)
    
    # Réponse KKiaPay
    kkiapay_response = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Réponse complète de l'API KKiaPay"
    )

    # Champs enrichis pour intégration complète
    webhook_received_at = models.DateTimeField(null=True, blank=True, help_text="Horodatage réception webhook")
    error_details = models.JSONField(default=dict, blank=True, help_text="Détails d'erreur structurés")
    retry_count = models.PositiveIntegerField(default=0, help_text="Nombre de tentatives webhook/API")
    callback_url = models.URLField(max_length=300, blank=True, null=True, help_text="URL de callback utilisée pour cette transaction")
    metadata = models.JSONField(default=dict, blank=True, help_text="Métadonnées métier/contextuelles")
    kkiapay_fees = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Frais KKiaPay prélevés")
    net_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, help_text="Montant net après frais")
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Informations d'erreur
    error_code = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)
    
    # Webhooks
    webhook_received = models.BooleanField(default=False)
    webhook_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['reference_tontiflex']),
            models.Index(fields=['reference_kkiapay']),
            models.Index(fields=['type_transaction', 'status']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = "Transaction KKiaPay"
        verbose_name_plural = "Transactions KKiaPay"
    
    def __str__(self):
        return f"{self.reference_tontiflex} - {self.get_type_transaction_display()} - {self.montant} {self.devise}"
    
    def is_success(self):
        """Vérifie si la transaction est réussie"""
        return self.status == 'success'
    
    def is_pending(self):
        """Vérifie si la transaction est en attente"""
        return self.status in ['pending', 'processing']
    
    def is_failed(self):
        """Vérifie si la transaction a échoué"""
        return self.status in ['failed', 'cancelled']
    
    def mark_as_success(self):
        """Marque la transaction comme réussie"""
        self.status = 'success'
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'processed_at', 'updated_at'])
    
    def mark_as_failed(self, error_code="", error_message=""):
        """Marque la transaction comme échouée"""
        self.status = 'failed'
        self.error_code = error_code
        self.error_message = error_message
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'error_code', 'error_message', 'processed_at', 'updated_at'])
    
    def generate_reference(self):
        """Génère une référence unique TontiFlex"""
        if not self.reference_tontiflex:
            import random
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            type_prefix = self.type_transaction[:3].upper()
            random_id = str(random.randint(1000, 9999))
            self.reference_tontiflex = f"TF{type_prefix}{timestamp}{random_id}"
    
    def save(self, *args, **kwargs):
        """Override save pour générer la référence automatiquement"""
        if not self.reference_tontiflex:
            self.generate_reference()
        super().save(*args, **kwargs)
