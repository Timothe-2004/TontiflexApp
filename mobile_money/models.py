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
Modèles pour la gestion des paiements Mobile Money dans TontiFlex.
Support pour MTN Mobile Money, Moov Money et autres opérateurs.
"""
from django.db import models
from django.core.validators import MinValueValidator, RegexValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
import uuid
import secrets
import string


class OperateurMobileMoney(models.Model):
    """
    Configuration des opérateurs de Mobile Money supportés.
    """
    
    
    nom = models.CharField(
        max_length=50,
        unique=True,
        help_text="Nom de l'opérateur (ex: MTN, Moov, Orange)"
    )
    
    code = models.CharField(
        max_length=10,
        unique=True,
        help_text="Code court de l'opérateur (ex: MTN, MOOV)"
    )
    
    prefixes_telephone = models.JSONField(
        default=list,
        help_text="Préfixes téléphoniques supportés par cet opérateur"
    )
    
    api_base_url = models.URLField(
        help_text="URL de base de l'API de l'opérateur"
    )
    
    api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="Clé API pour l'authentification"
    )
    
    api_secret = models.CharField(
        max_length=255,
        blank=True,
        help_text="Secret API pour l'authentification"
    )
    
    merchant_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Identifiant marchand"
    )
    
    frais_fixe = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Frais fixe par transaction"
    )
    
    frais_pourcentage = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.0000'),
        validators=[MinValueValidator(Decimal('0.0000'))],
        help_text="Frais en pourcentage du montant"
    )
    
    montant_minimum = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[MinValueValidator(Decimal('1.00'))],
        help_text="Montant minimum par transaction"
    )
    
    montant_maximum = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('1000000.00'),
        validators=[MinValueValidator(Decimal('1.00'))],
        help_text="Montant maximum par transaction"
    )
    
    
    
    webhook_url = models.URLField(
        blank=True,
        help_text="URL de callback pour les notifications"
    )
    
    timeout_secondes = models.PositiveIntegerField(
        default=300,
        help_text="Timeout en secondes pour les requêtes API"
    )
    
    date_creation = models.DateTimeField(
        default=timezone.now,
        help_text="Date de création"
    )
    
    date_modification = models.DateTimeField(
        auto_now=True,
        help_text="Date de dernière modification"
    )
    
    class Meta:
        verbose_name = "Opérateur Mobile Money"
        verbose_name_plural = "Opérateurs Mobile Money"
        ordering = ['nom']
    
    def __str__(self):
        return f"{self.nom} ({self.code})"
    
    def calculer_frais(self, montant):
        """Calcule les frais pour un montant donné."""
        frais_pourcentage = montant * (self.frais_pourcentage / 100)
        return self.frais_fixe + frais_pourcentage
    
    def valider_montant(self, montant):
        """Valide qu'un montant est dans les limites de l'opérateur."""
        if montant < self.montant_minimum:
            raise ValidationError(f"Montant minimum : {self.montant_minimum} FCFA")
        if montant > self.montant_maximum:
            raise ValidationError(f"Montant maximum : {self.montant_maximum} FCFA")
    
    def valider_telephone(self, numero):
        """Valide qu'un numéro de téléphone correspond aux préfixes supportés."""
        for prefix in self.prefixes_telephone:
            if numero.startswith(prefix):
                return True
        return False


class TransactionMobileMoney(models.Model):
    lien_paiement = models.URLField(
        blank=True,
        null=True,
        help_text="Lien de paiement web Mobile Money (MTN) à transmettre à l'utilisateur"
    )
    """
    Gestion des transactions Mobile Money.
    """
    
    class TypeTransactionChoices(models.TextChoices):
        DEPOT = 'depot', 'Dépôt'
        RETRAIT = 'retrait', 'Retrait'
        TRANSFERT = 'transfert', 'Transfert'
        PAIEMENT = 'paiement', 'Paiement'
        REMBOURSEMENT = 'remboursement', 'Remboursement'
    
    class StatutChoices(models.TextChoices):
        INITIE = 'initie', 'Initié'
        EN_ATTENTE = 'en_attente', 'En attente de confirmation'
        EN_COURS = 'en_cours', 'En cours de traitement'
        SUCCES = 'succes', 'Succès'
        ECHEC = 'echec', 'Échec'
        EXPIRE = 'expire', 'Expiré'
        ANNULE = 'annule', 'Annulé'
        REMBOURSE = 'rembourse', 'Remboursé'
    
    # Identifiants
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identifiant unique de la transaction"
    )
    
    reference_interne = models.CharField(
        max_length=50,
        unique=True,
        help_text="Référence interne TontiFlex"
    )
    
    reference_operateur = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Référence fournie par l'opérateur"
    )
    
    # Détails de la transaction
    type_transaction = models.CharField(
        max_length=15,
        choices=TypeTransactionChoices.choices,
        help_text="Type de transaction"
    )
    
    # Nouveau champ pour identifier les commissions SFD
    is_commission = models.BooleanField(
        default=False,
        help_text="True si cette transaction est une commission SFD (première mise de cycle)"
    )
    
    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1.00'))],
        help_text="Montant de la transaction en FCFA"
    )
    
    frais = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Frais de la transaction"
    )
    
    montant_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Montant total (montant + frais)"
    )
    
    # Informations client
    numero_telephone = models.CharField(
        max_length=15,
        validators=[
            RegexValidator(
                regex=r'^\+?[0-9]{8,15}$',
                message="Format de numéro de téléphone invalide"
            )
        ],
        help_text="Numéro de téléphone du client"
    )
    
    nom_client = models.CharField(
        max_length=100,
        help_text="Nom du client"
    )
    
    # Statut et suivi
    statut = models.CharField(
        max_length=15,
        choices=StatutChoices.choices,
        default=StatutChoices.INITIE,
        help_text="Statut de la transaction"
    )
    
    operateur = models.ForeignKey(
        OperateurMobileMoney,
        on_delete=models.PROTECT,
        related_name='transactions',
        help_text="Opérateur Mobile Money utilisé"
    )
    
    # Relations TontiFlex
    client = models.ForeignKey(
        'accounts.Client',
        on_delete=models.CASCADE,
        related_name='transactions_mobile_money',
        help_text="Client TontiFlex"
    )
    
    transaction_tontiflex = models.OneToOneField(
        'mobile_money.TransactionMobileMoney',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='transaction_mobile_money',
        help_text="Transaction Mobile Money associée"
    )
    
    # Métadonnées
    description = models.TextField(
        blank=True,
        help_text="Description de la transaction"
    )
    
    callback_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Données reçues du callback de l'opérateur"
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Métadonnées additionnelles"
    )
    
    # Gestion du temps
    date_creation = models.DateTimeField(
        default=timezone.now,
        help_text="Date de création de la transaction"
    )
    
    date_expiration = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date d'expiration de la transaction"
    )
    
    date_completion = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de completion de la transaction"
    )
    
    devise = models.CharField(
        max_length=3,
        default='XOF',
        help_text="Code devise (XOF pour FCFA)"
    )
    
    reponse_operateur = models.JSONField(
        default=dict,
        blank=True,
        help_text="Réponse complète de l'API opérateur"
    )
    
    message_erreur = models.TextField(
        blank=True,
        help_text="Message d'erreur si échec"
    )
    
    date_modification = models.DateTimeField(
        auto_now=True,
        help_text="Date de dernière modification"
    )
    
    # Tentatives et retry
    nombre_tentatives = models.PositiveIntegerField(
        default=0,
        help_text="Nombre de tentatives de traitement"
    )
    
    derniere_erreur = models.TextField(
        blank=True,
        help_text="Dernière erreur rencontrée"
    )
    
    class Meta:
        verbose_name = "Transaction Mobile Money"
        verbose_name_plural = "Transactions Mobile Money"
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['reference_interne']),
            models.Index(fields=['reference_operateur']),
            models.Index(fields=['statut']),
            models.Index(fields=['numero_telephone']),
            models.Index(fields=['date_creation']),
        ]
    
    def __str__(self):
        return f"{self.reference_interne} - {self.montant} FCFA - {self.get_statut_display()}"
    
    def save(self, *args, **kwargs):
        # Générer une référence interne si elle n'existe pas
        if not self.reference_interne:
            self.reference_interne = self.generer_reference_interne()
        
        # S'assurer que montant et frais sont des Decimal
        if not isinstance(self.montant, Decimal):
            self.montant = Decimal(str(self.montant))
        if not isinstance(self.frais, Decimal):
            self.frais = Decimal(str(self.frais))
        
        # Calculer le montant total
        self.montant_total = self.montant + self.frais
        
        super().save(*args, **kwargs)
    
    def generer_reference_interne(self):
        """Génère une référence interne unique."""
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        return f"TF{timestamp}{random_part}"
    
    def est_expire(self):
        """Vérifie si la transaction a expiré."""
        if self.date_expiration:
            return timezone.now() > self.date_expiration
        return False
    
    def peut_etre_relancee(self):
        """Vérifie si la transaction peut être relancée."""
        return self.statut in [
            self.StatutChoices.INITIE,
            self.StatutChoices.ECHEC,
            self.StatutChoices.EXPIRE
        ] and not self.est_expire()


class LogTransactionMobileMoney(models.Model):
    """
    Journalisation des événements des transactions Mobile Money.
    """
    
    class TypeEvenementChoices(models.TextChoices):
        CREATION = 'creation', 'Création'
        ENVOI_API = 'envoi_api', 'Envoi API'
        REPONSE_API = 'reponse_api', 'Réponse API'
        CALLBACK = 'callback', 'Callback reçu'
        CHANGEMENT_STATUT = 'changement_statut', 'Changement de statut'
        ERREUR = 'erreur', 'Erreur'
        RETRY = 'retry', 'Nouvelle tentative'
    
    transaction = models.ForeignKey(
        TransactionMobileMoney,
        on_delete=models.CASCADE,
        related_name='logs',
        help_text="Transaction concernée"
    )
    
    type_evenement = models.CharField(
        max_length=20,
        choices=TypeEvenementChoices.choices,
        help_text="Type d'événement"
    )
    
    ancien_statut = models.CharField(
        max_length=15,
        blank=True,
        help_text="Ancien statut (pour les changements de statut)"
    )
    
    nouveau_statut = models.CharField(
        max_length=15,
        blank=True,
        help_text="Nouveau statut (pour les changements de statut)"
    )
    
    message = models.TextField(
        help_text="Message ou description de l'événement"
    )
    
    donnees = models.JSONField(
        default=dict,
        blank=True,
        help_text="Données additionnelles de l'événement"
    )
    
    date_creation = models.DateTimeField(
        default=timezone.now,
        help_text="Date de l'événement"
    )
    
    class Meta:
        verbose_name = "Log Transaction Mobile Money"
        verbose_name_plural = "Logs Transactions Mobile Money"
        ordering = ['-date_creation']
    
    def __str__(self):
        return f"{self.transaction.reference_interne} - {self.get_type_evenement_display()}"


class ConfigurationWebhook(models.Model):
    """
    Configuration des webhooks pour les callbacks des opérateurs.
    """
    
    operateur = models.OneToOneField(
        OperateurMobileMoney,
        on_delete=models.CASCADE,
        related_name='configuration_webhook',
        help_text="Opérateur associé"
    )
    
    url_callback = models.URLField(
        help_text="URL de callback configurée chez l'opérateur"
    )
    
    secret_webhook = models.CharField(
        max_length=255,
        help_text="Secret pour valider l'authenticité des callbacks"
    )
    
    methode_authentification = models.CharField(
        max_length=50,
        default='signature_hmac',
        help_text="Méthode d'authentification des webhooks"
    )
    
    actif = models.BooleanField(
        default=True,
        help_text="Si le webhook est actif"
    )
    
    date_creation = models.DateTimeField(
        default=timezone.now,
        help_text="Date de création"
    )
    
    date_modification = models.DateTimeField(
        auto_now=True,
        help_text="Date de modification"
    )
    
    class Meta:
        verbose_name = "Configuration Webhook"
        verbose_name_plural = "Configurations Webhooks"
    
    def __str__(self):
        return f"Webhook {self.operateur.nom}"
