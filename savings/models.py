from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
import uuid
import logging

logger = logging.getLogger(__name__)


class SavingsAccount(models.Model):
    """
    Modèle représentant un compte épargne dans le système TontiFlex.
    Un compte épargne permet aux clients d'effectuer des dépôts et retraits
    via Mobile Money après validation par un agent SFD.
    
    Workflow de création:
    1. Client soumet demande avec documents (en_cours_creation)
    2. Agent SFD valide documents (validee_agent) 
    3. Client paie frais création Mobile Money (paiement_effectue)
    4. Système active compte automatiquement (actif)
    """
    
    # Choix pour le statut du compte
    class StatutChoices(models.TextChoices):
        EN_COURS_CREATION = 'en_cours_creation', 'En cours de création'
        VALIDEE_AGENT = 'validee_agent', 'Validée par agent'
        PAIEMENT_EFFECTUE = 'paiement_effectue', 'Paiement effectué'
        ACTIF = 'actif', 'Actif'
        SUSPENDU = 'suspendu', 'Suspendu'
        FERME = 'ferme', 'Fermé'
        REJETE = 'rejete', 'Rejeté'
    
    # Choix pour les opérateurs Mobile Money
    class OperateurChoices(models.TextChoices):
        MTN = 'mtn', 'MTN Mobile Money'
        MOOV = 'moov', 'Moov Money'
        ORANGE = 'orange', 'Orange Money'
    
    # =============================================================================
    # SECTION 1: IDENTIFIANTS ET RELATIONS
    # =============================================================================
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identifiant unique du compte épargne"
    )
    
    client = models.OneToOneField(
        'accounts.Client',
        on_delete=models.CASCADE,
        related_name='compte_epargne',
        help_text="Client propriétaire du compte épargne"
    )
    
    agent_validateur = models.ForeignKey(
        'accounts.AgentSFD',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='comptes_epargne_valides',
        help_text="Agent SFD ayant validé la demande de création"
    )
    
    # =============================================================================
    # SECTION 2: STATUT ET WORKFLOW
    # =============================================================================
    
    statut = models.CharField(
        max_length=20,
        choices=StatutChoices.choices,
        default=StatutChoices.EN_COURS_CREATION,
        help_text="Statut actuel du compte épargne"
    )
    
    # =============================================================================
    # SECTION 3: DOCUMENTS REQUIS
    # =============================================================================
    
    piece_identite = models.FileField(
        upload_to='savings/documents/identite/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        help_text="Copie numérique de la pièce d'identité (CNI, Passeport, etc.)"
    )
    
    photo_identite = models.FileField(
        upload_to='savings/documents/photos/',
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])],
        help_text="Photo d'identité du client"
    )
    
    # =============================================================================
    # SECTION 4: MOBILE MONEY ET PAIEMENT
    # =============================================================================
    
    numero_telephone_paiement = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        help_text="Numéro de téléphone Mobile Money pour frais de création"
    )
    
    operateur_mobile_money = models.CharField(
        max_length=10,
        choices=OperateurChoices.choices,
        null=True,
        blank=True,
        help_text="Opérateur Mobile Money choisi pour les transactions"
    )
    
    frais_creation = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('500.00')),
            MaxValueValidator(Decimal('5000.00'))
        ],
        default=Decimal('1000.00'),
        help_text="Frais de création du compte épargne en FCFA"
    )
    
    transaction_frais_creation = models.ForeignKey(
        'payments.KKiaPayTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='comptes_epargne_crees',
        help_text="Transaction KKiaPay pour les frais de création"
    )
    
    # =============================================================================
    # SECTION 5: MÉTADONNÉES TEMPORELLES
    # =============================================================================
    
    date_demande = models.DateTimeField(
        default=timezone.now,
        help_text="Date de soumission de la demande de création"
    )
    
    date_validation_agent = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de validation par l'agent SFD"
    )
    
    date_paiement_frais = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de paiement des frais de création"
    )
    
    date_activation = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date d'activation du compte épargne"
    )
    
    date_modification = models.DateTimeField(
        auto_now=True,
        help_text="Date de dernière modification"
    )
    
    # =============================================================================
    # SECTION 6: CHAMPS COMPLÉMENTAIRES
    # =============================================================================
    
    commentaires_agent = models.TextField(
        max_length=1000,
        blank=True,
        null=True,
        help_text="Commentaires de l'agent lors de la validation"
    )
    
    raison_rejet = models.TextField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Raison du rejet si applicable"
    )
    
    # =============================================================================
    # PROPRIÉTÉS ET MÉTADONNÉES
    # =============================================================================
    
    @property
    def sfd(self):
        """
        Retourne la SFD associée à ce compte épargne via l'agent validateur.
        
        Returns:
            SFD: SFD gestionnaire du compte ou None si pas encore validé
        """
        if self.agent_validateur and self.agent_validateur.sfd:
            return self.agent_validateur.sfd
        return None
    
    @property
    def nom_sfd(self):
        """
        Retourne le nom de la SFD gestionnaire du compte.
        
        Returns:
            str: Nom de la SFD ou 'Non définie'
        """
        if self.sfd:
            return self.sfd.nom
        return 'Non définie'
    
    @property  
    def solde_disponible(self):
        """
        Propriété pour accéder facilement au solde calculé.
        
        Returns:
            Decimal: Solde disponible du compte
        """
        return self.calculer_solde()

    class Meta:
        db_table = 'savings_account'
        verbose_name = 'Compte Épargne'
        verbose_name_plural = 'Comptes Épargne'
        ordering = ['-date_demande']
        indexes = [
            models.Index(fields=['statut']),
            models.Index(fields=['client']),
            models.Index(fields=['agent_validateur']),
            models.Index(fields=['date_demande']),
        ]
    
    def __str__(self):
        return f"Compte épargne {self.client.nom_complet} - {self.get_statut_display()}"
    
    # =============================================================================
    # MÉTHODES MÉTIER
    # =============================================================================
    
    def calculer_solde(self):
        """
        Calcule le solde actuel du compte épargne.
        
        Returns:
            Decimal: Solde disponible (dépôts - retraits)
        """
        try:
            if self.statut != self.StatutChoices.ACTIF:
                return Decimal('0.00')
            
            # Calculer total des dépôts confirmés
            total_depots = self.transactions.filter(
                type_transaction=SavingsTransaction.TypeChoices.DEPOT,
                statut=SavingsTransaction.StatutChoices.CONFIRMEE
            ).aggregate(
                total=models.Sum('montant')
            )['total'] or Decimal('0.00')
            
            # Calculer total des retraits confirmés  
            total_retraits = self.transactions.filter(
                type_transaction=SavingsTransaction.TypeChoices.RETRAIT,
                statut=SavingsTransaction.StatutChoices.CONFIRMEE
            ).aggregate(
                total=models.Sum('montant')
            )['total'] or Decimal('0.00')
            
            return total_depots - total_retraits
            
        except Exception as e:
            logger.error(f"Erreur calcul solde compte {self.id}: {e}")
            return Decimal('0.00')
    
    def activer_compte(self):
        """
        Active le compte épargne après paiement des frais.
        
        Returns:
            bool: True si activation réussie, False sinon
        """
        try:
            if (self.statut == self.StatutChoices.PAIEMENT_EFFECTUE and 
                self.transaction_frais_creation and 
                self.transaction_frais_creation.status == 'success'):
                
                self.statut = self.StatutChoices.ACTIF
                self.date_activation = timezone.now()
                self.save()
                
                logger.info(f"Compte épargne {self.id} activé pour client {self.client.id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur activation compte {self.id}: {e}")
            return False
    
    def suspendre_compte(self, raison=""):
        """
        Suspend le compte épargne.
        
        Args:
            raison (str): Raison de la suspension
            
        Returns:
            bool: True si suspension réussie, False sinon
        """
        try:
            if self.statut == self.StatutChoices.ACTIF:
                self.statut = self.StatutChoices.SUSPENDU
                self.raison_rejet = raison
                self.save()
                
                logger.info(f"Compte épargne {self.id} suspendu: {raison}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur suspension compte {self.id}: {e}")
            return False
    
    def peut_effectuer_transaction(self, montant, type_transaction):
        """
        Vérifie si une transaction peut être effectuée.
        
        Args:
            montant (Decimal): Montant de la transaction
            type_transaction (str): Type (depot ou retrait)
            
        Returns:
            bool: True si transaction possible, False sinon
        """
        try:
            # Compte doit être actif
            if self.statut != self.StatutChoices.ACTIF:
                return False
            
            # Montant doit être positif
            if montant <= 0:
                return False
            
            # Pour retrait, vérifier solde suffisant
            if type_transaction == SavingsTransaction.TypeChoices.RETRAIT:
                solde_actuel = self.calculer_solde()
                if montant > solde_actuel:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur vérification transaction compte {self.id}: {e}")
            return False
    
    @property
    def prochaine_action_requise(self):
        """
        Détermine la prochaine action requise selon le statut.
        
        Returns:
            str: Description de la prochaine action
        """
        actions = {
            self.StatutChoices.EN_COURS_CREATION: "Validation par agent SFD",
            self.StatutChoices.VALIDEE_AGENT: "Paiement frais de création",
            self.StatutChoices.PAIEMENT_EFFECTUE: "Activation automatique en cours",
            self.StatutChoices.ACTIF: "Compte opérationnel",
            self.StatutChoices.SUSPENDU: "Régularisation requise",
            self.StatutChoices.FERME: "Aucune action possible",
            self.StatutChoices.REJETE: "Soumettre nouvelle demande"
        }
        return actions.get(self.statut, "Action inconnue")


class SavingsTransaction(models.Model):
    """
    Modèle représentant une transaction sur un compte épargne.
    Supporte les dépôts et retraits via Mobile Money.
    """
    
    # Choix pour le type de transaction
    class TypeChoices(models.TextChoices):
        DEPOT = 'depot', 'Dépôt'
        RETRAIT = 'retrait', 'Retrait'
    
    # Choix pour le statut de transaction
    class StatutChoices(models.TextChoices):
        EN_COURS = 'en_cours', 'En cours'
        CONFIRMEE = 'confirmee', 'Confirmée'
        ECHOUEE = 'echouee', 'Échouée'
        ANNULEE = 'annulee', 'Annulée'
    
    # =============================================================================
    # SECTION 1: IDENTIFIANTS ET RELATIONS
    # =============================================================================
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identifiant unique de la transaction"
    )
    
    compte_epargne = models.ForeignKey(
        SavingsAccount,
        on_delete=models.CASCADE,
        related_name='transactions',
        help_text="Compte épargne concerné par la transaction"
    )
    
    transaction_kkiapay = models.OneToOneField(
        'payments.KKiaPayTransaction',
        on_delete=models.CASCADE,
        related_name='transaction_epargne',
        help_text="Transaction KKiaPay associée"
    )
    
    # =============================================================================
    # SECTION 2: DÉTAILS DE LA TRANSACTION
    # =============================================================================
    
    type_transaction = models.CharField(
        max_length=10,
        choices=TypeChoices.choices,
        help_text="Type de transaction (dépôt ou retrait)"
    )
    
    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('100.00'))],
        help_text="Montant de la transaction en FCFA"
    )
    
    statut = models.CharField(
        max_length=15,
        choices=StatutChoices.choices,
        default=StatutChoices.EN_COURS,
        help_text="Statut de la transaction"
    )
    
    # =============================================================================
    # SECTION 3: MOBILE MONEY
    # =============================================================================
    
    numero_telephone = models.CharField(
        max_length=15,
        help_text="Numéro de téléphone Mobile Money"
    )
    
    operateur = models.CharField(
        max_length=10,
        choices=SavingsAccount.OperateurChoices.choices,
        help_text="Opérateur Mobile Money utilisé"
    )
    
    # =============================================================================
    # SECTION 4: MÉTADONNÉES
    # =============================================================================
    
    date_transaction = models.DateTimeField(
        default=timezone.now,
        help_text="Date d'initiation de la transaction"
    )
    
    date_confirmation = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de confirmation de la transaction"
    )
    
    commentaires = models.TextField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Commentaires sur la transaction"
    )
    
    class Meta:
        db_table = 'savings_transaction'
        verbose_name = 'Transaction Épargne'
        verbose_name_plural = 'Transactions Épargne'
        ordering = ['-date_transaction']
        indexes = [
            models.Index(fields=['compte_epargne', 'type_transaction']),
            models.Index(fields=['statut']),
            models.Index(fields=['date_transaction']),
        ]
    
    def __str__(self):
        return f"{self.get_type_transaction_display()} {self.montant} FCFA - {self.compte_epargne.client.nom_complet}"
    
    # =============================================================================
    # MÉTHODES MÉTIER
    # =============================================================================
    
    def confirmer_transaction(self):
        """
        Confirme la transaction après succès Mobile Money.
        
        Returns:
            bool: True si confirmation réussie, False sinon
        """
        try:
            if (self.statut == self.StatutChoices.EN_COURS and 
                self.transaction_kkiapay.status == 'success'):
                
                self.statut = self.StatutChoices.CONFIRMEE
                self.date_confirmation = timezone.now()
                self.save()
                
                logger.info(f"Transaction épargne {self.id} confirmée")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur confirmation transaction {self.id}: {e}")
            return False
    
    def annuler_transaction(self, raison=""):
        """
        Annule la transaction.
        
        Args:
            raison (str): Raison de l'annulation
            
        Returns:
            bool: True si annulation réussie, False sinon
        """
        try:
            if self.statut == self.StatutChoices.EN_COURS:
                self.statut = self.StatutChoices.ANNULEE
                self.commentaires = raison
                self.save()
                
                logger.info(f"Transaction épargne {self.id} annulée: {raison}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur annulation transaction {self.id}: {e}")
            return False
