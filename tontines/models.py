from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
import uuid
import logging


class Tontine(models.Model):
    """
    Modèle représentant une tontine dans le système TontiFlex.
    Une tontine permet aux clients de cotiser collectivement 
    et d'effectuer des retraits selon des règles définies.
    """
    
   
    # Choix pour le statut
    class StatutChoices(models.TextChoices):
        ACTIVE = 'active', 'Active'
        FERMEE = 'fermee', 'Fermée'
        SUSPENDUE = 'suspendue', 'Suspendue'
    
    # Attributs principaux
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identifiant unique de la tontine"
    )
    
    nom = models.CharField(
        max_length=200,
        help_text="Nom de la tontine"    )
    
    
    montantMinMise = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1.00'))],  # Réduit à 1 FCFA
        help_text="Montant minimum de la mise quotidienne en FCFA"
    )
    
    montantMaxMise = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1.00'))],  # Réduit à 1 FCFA
        help_text="Montant maximum de la mise quotidienne en FCFA"
    )
    

    
    reglesRetrait = models.JSONField(
        default=dict,
        help_text="Règles de retrait définies pour cette tontine"
    )
    

    
    dateCreation = models.DateTimeField(
        default=timezone.now,
        help_text="Date de création de la tontine"
    )
    
    statut = models.CharField(
        max_length=15,
        choices=StatutChoices.choices,
        default=StatutChoices.ACTIVE,
        help_text="Statut de la tontine"    )
    fraisAdhesion = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('1.00')),  # Réduit à 1 FCFA
            MaxValueValidator(Decimal('5000.00'))
        ],
        default=Decimal('1.00'),  # Valeur par défaut réduite à 1 FCFA
        help_text="Frais d'adhésion à la tontine en FCFA"
    )
    
    # Relations
    participants = models.ManyToManyField(
        'accounts.Client',
        through='TontineParticipant',
        related_name='tontines_participees',
        blank=True,
        help_text="Clients participants à cette tontine"
    )

    administrateurId = models.ForeignKey(
        'accounts.AdministrateurSFD',
        on_delete=models.PROTECT,
        related_name='tontines_administrees',
        help_text="Administrateur SFD responsable de cette tontine"
    )
    
    # Métadonnées
    date_modification = models.DateTimeField(
        auto_now=True,
        help_text="Date de dernière modification"
    )
    
    class Meta:
        verbose_name = "Tontine"
        verbose_name_plural = "Tontines"
        ordering = ['-dateCreation']
        db_table = 'tontines_tontine'
    
    def __str__(self):
        return f"{self.nom} ({self.get_type_display()}) - {self.statut}"
    
    def clean(self):
        """Validation des données de la tontine"""
        super().clean()
        
        # Vérifier que montantMaxMise >= montantMinMise
        if self.montantMaxMise <= self.montantMinMise:
            raise ValidationError({
                'montantMaxMise': 'Le montant maximum doit être supérieur au montant minimum.'
            })
    
    def save(self, *args, **kwargs):
        """Override save pour effectuer des validations"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    # Méthodes métier
    
    def ajouterParticipant(self, client, montantMise):
        """
        Ajoute un participant à la tontine.
        
        Args:
            client (Client): Client à ajouter
            montantMise (Decimal): Montant de sa mise quotidienne
            
        Returns:
            bool: True si ajout réussi, False sinon
        """
        try:
            # Vérifier que le client n'est pas déjà participant
            if self.participants.filter(id=client.id).exists():
                return False
            
            # Vérifier que la tontine est active
            if self.statut != self.StatutChoices.ACTIVE:
                return False
            
            # Vérifier les limites de mise
            if not self.verifierLimitesMise(montantMise):
                return False
            
            # Créer la relation participant
            TontineParticipant.objects.create(
                tontine=self,
                client=client,
                montantMise=montantMise,
                dateAdhesion=timezone.now(),
                statut='actif'
            )
            
            return True
            
        except Exception:
            return False
    
    def retirerParticipant(self, clientId):
        """
        Retire un participant de la tontine.
        
        Args:
            clientId (str): ID du client à retirer
            
        Returns:
            bool: True si retrait réussi, False sinon
        """
        try:
            participant = TontineParticipant.objects.get(
                tontine=self,
                client_id=clientId,
                statut='actif'
            )
            
            # Marquer comme inactif au lieu de supprimer
            participant.statut = 'inactif'
            participant.dateRetrait = timezone.now()
            participant.save()
            
            return True
            
        except TontineParticipant.DoesNotExist:
            return False
        except Exception:
            return False
    
    def calculerSoldeTotal(self):
        """
        Calcule le solde total de la tontine.
        
        Returns:
            Decimal: Solde total de la tontine
        """
        try:
            # Calculer le total des cotisations confirmées
            total_cotisations = Cotisation.objects.filter(
                tontine=self,
                statut='confirmee'
            ).aggregate(
                total=models.Sum('montant')
            )['total'] or Decimal('0.00')
            
            # Calculer le total des retraits confirmés
            total_retraits = Retrait.objects.filter(
                tontine=self,
                statut='confirmee'
            ).aggregate(
                total=models.Sum('montant')
            )['total'] or Decimal('0.00')
            
            return total_cotisations - total_retraits
            
        except Exception:
            return Decimal('0.00')
    
    def calculerSoldeClient(self, clientId):
        """
        Calcule le solde d'un client spécifique dans cette tontine.
        
        Args:
            clientId (str): ID du client
            
        Returns:
            Decimal: Solde du client dans cette tontine
        """
        try:
            # Calculer les cotisations du client
            cotisations_client = Cotisation.objects.filter(
                tontine=self,
                client_id=clientId,
                statut='confirmee'
            ).aggregate(
                total=models.Sum('montant')
            )['total'] or Decimal('0.00')
            
            # Calculer les retraits du client
            retraits_client = Retrait.objects.filter(
                tontine=self,
                client_id=clientId,
                statut='confirmee'
            ).aggregate(
                total=models.Sum('montant')
            )['total'] or Decimal('0.00')
            
            return cotisations_client - retraits_client
            
        except Exception:
            return Decimal('0.00')
    
    def verifierLimitesMise(self, montant):
        """
        Vérifie si un montant respecte les limites de mise.
        
        Args:
            montant (Decimal): Montant à vérifier
            
        Returns:
            bool: True si dans les limites, False sinon
        """
        try:
            return self.montantMinMise <= montant <= self.montantMaxMise
        except Exception:
            return False
    
    def fermerTontine(self):
        """
        Ferme la tontine et désactive tous les participants.
        
        Returns:
            bool: True si fermeture réussie, False sinon
        """
        try:
            # Changer le statut de la tontine
            self.statut = self.StatutChoices.FERMEE
            self.save()
            
            # Désactiver tous les participants actifs
            TontineParticipant.objects.filter(
                tontine=self,
                statut='actif'
            ).update(
                statut='inactif',
                dateRetrait=timezone.now()
            )
            
            return True
            
        except Exception:
            return False
    
    def genererCycleCotisation(self):
        """
        Génère un nouveau cycle de cotisation basé sur la périodicité.
        
        Returns:
            dict: Informations sur le cycle généré
        """
        try:
            from datetime import timedelta
            
            # Calcul basé sur la périodicité
            if self.periodicite == self.PeriodiciteChoices.QUOTIDIENNE:
                duree_cycle = 31  # Cycle TontiFlex standard
            elif self.periodicite == self.PeriodiciteChoices.HEBDOMADAIRE:
                duree_cycle = 7
            elif self.periodicite == self.PeriodiciteChoices.MENSUELLE:
                duree_cycle = 30
            else:
                duree_cycle = 31
            
            date_debut = timezone.now().date()
            date_fin = date_debut + timedelta(days=duree_cycle)
            
            return {
                'date_debut': date_debut,
                'date_fin': date_fin,
                'duree_jours': duree_cycle,
                'periodicite': self.get_periodicite_display()
            }
            
        except Exception:
            return {}
    
    def consulterStatistiques(self):
        """
        Génère les statistiques de la tontine.
        
        Returns:
            dict: Statistiques de la tontine
        """
        try:
            participants_actifs = TontineParticipant.objects.filter(
                tontine=self,
                statut='actif'
            ).count()
            
            total_cotisations = Cotisation.objects.filter(
                tontine=self
            ).count()
            
            total_retraits = Retrait.objects.filter(
                tontine=self
            ).count()
            
            solde_total = self.calculerSoldeTotal()
            
            return {
                'participants_actifs': participants_actifs,
                'total_cotisations': total_cotisations,
                'total_retraits': total_retraits,
                'solde_total': solde_total,
                'frais_adhesion': self.fraisAdhesion,
                'duree_restante': self.duree,  # À calculer selon la date de création
                'statut': self.get_statut_display()
            }
            
        except Exception:
            return {}
    
    @property
    def nombre_participants(self):
        """Retourne le nombre de participants actifs"""
        return TontineParticipant.objects.filter(
            tontine=self,
            statut='actif'
        ).count()
    
    @property
    def est_active(self):
        """Vérifie si la tontine est active"""
        return self.statut == self.StatutChoices.ACTIVE
    
    def calculer_total_cotisations_client(self, client):
        """
        Calcule le total des cotisations d'un client spécifique dans cette tontine.
        
        Args:
            client: Objet Client ou ID du client
            
        Returns:
            Decimal: Total des cotisations confirmées du client        """
        try:
            client_id = client.id if hasattr(client, 'id') else client
            
            total = Cotisation.objects.filter(
                tontine=self,
                client_id=client_id,
                statut='confirmee'
            ).aggregate(
                total=models.Sum('montant')
            )['total'] or Decimal('0.00')
            
            return total
            
        except Exception:
            return Decimal('0.00')
    
    def calculer_total_retraits_client(self, client):
        """
        Calcule le total des retraits d'un client spécifique dans cette tontine.
        
        Args:
            client: Objet Client ou ID du client
            
        Returns:
            Decimal: Total des retraits confirmés du client
        """
        try:
            client_id = client.id if hasattr(client, 'id') else client
            
            total = Retrait.objects.filter(
                tontine=self,
                client_id=client_id,
                statut='confirmee'
            ).aggregate(
                total=models.Sum('montant')
            )['total'] or Decimal('0.00')
            
            return total
            
        except Exception:
            return Decimal('0.00')

class TontineParticipant(models.Model):
    """
    Modèle intermédiaire pour la relation many-to-many entre Tontine et Client.
    Stocke les informations spécifiques à la participation d'un client à une tontine.
    """
    
    class StatutParticipantChoices(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        INACTIF = 'inactif', 'Inactif'
        SUSPENDU = 'suspendu', 'Suspendu'
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    tontine = models.ForeignKey(
        Tontine,
        on_delete=models.CASCADE,
        help_text="Tontine concernée"
    )
    
    client = models.ForeignKey(
        'accounts.Client',
        on_delete=models.CASCADE,
        help_text="Client participant"
    )
    
    montantMise = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Montant de la mise quotidienne du client"
    )
    
    dateAdhesion = models.DateTimeField(
        default=timezone.now,
        help_text="Date d'adhésion à la tontine"
    )
    
    dateRetrait = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de retrait de la tontine"
    )
    
    statut = models.CharField(
        max_length=15,
        choices=StatutParticipantChoices.choices,
        default=StatutParticipantChoices.ACTIF,
        help_text="Statut du participant"
    )
    
    # Champs pour KKiaPay (remplace Mobile Money)
    fraisAdhesionPayes = models.BooleanField(
        default=False,
        help_text="Indique si les frais d'adhésion ont été payés"
    )
    
    transactionAdhesion = models.ForeignKey(
        'payments.KKiaPayTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='adhesions_associees',
        help_text="Transaction KKiaPay pour les frais d'adhésion"
    )
    
    def calculer_solde_disponible(self):
        """Calcule le solde disponible du participant pour retrait."""
        try:
            # Total des cotisations confirmées
            cotisations_total = Cotisation.objects.filter(
                client=self.client,
                tontine=self.tontine,
                statut='confirmee'
            ).aggregate(
                total=models.Sum('montant')
            )['total'] or Decimal('0.00')
            
            # Total des retraits confirmés
            retraits_total = Retrait.objects.filter(
                client=self.client,
                tontine=self.tontine,
                statut__in=['approved', 'confirmee']
            ).aggregate(
                total=models.Sum('montant')
            )['total'] or Decimal('0.00')
            
            return cotisations_total - retraits_total
            
        except Exception:
            return Decimal('0.00')
    
    class Meta:
        verbose_name = "Participant Tontine"
        verbose_name_plural = "Participants Tontine"
        unique_together = [['tontine', 'client']]
        db_table = 'tontines_participant'
    
    def __str__(self):
        return f"{self.client.nom_complet} - {self.tontine.nom} ({self.statut})"
















































"""
Modèle unifié pour gérer à la fois la demande d'adhésion et son workflow.
WorkflowAdhesion devient le point d'entrée unique pour les clients.
"""

from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, FileExtensionValidator
from decimal import Decimal
import uuid
import logging

logger = logging.getLogger(__name__)


class Adhesion(models.Model):
    """
    Modèle unifié pour gérer la demande d'adhésion ET son workflow en 3 étapes :
    
    POINT D'ENTRÉE UNIQUE POUR LES CLIENTS
    
    1. Demande soumise (remplacement de DemandeAdhesion)
    2. Validation agent + Paiement frais
    3. Intégration tontine + Adhérent actif
    """
    
    STATUT_CHOICES = [
        ('demande_soumise', 'Demande soumise'),
        ('validee_agent', 'Validée par agent'),
        ('en_cours_paiement', 'En cours de paiement'),
        ('paiement_effectue', 'Paiement effectué'), 
        ('adherent', 'Adhérent actif'),
        ('rejetee', 'Rejetée'),
       
    ]
    
    ETAPES_CHOICES = [
        ('etape_1', 'Étape 1 - Validation agent'),
        ('etape_2', 'Étape 2 - Paiement frais'),
        ('etape_3', 'Étape 3 - Intégration tontine'),
    ]

    # =============================================================================
    # SECTION 1: IDENTIFIANTS ET RELATIONS
    # =============================================================================
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identifiant unique du workflow d'adhésion"
    )
    
    client = models.ForeignKey(
        'accounts.Client',
        on_delete=models.CASCADE,
        related_name='workflows_adhesion',
        help_text="Client demandant l'adhésion"
    )

    tontine = models.ForeignKey(
        'tontines.Tontine',
        on_delete=models.CASCADE,
        related_name='workflows_adhesion',
        help_text="Tontine à rejoindre"
    )

    agent_validateur = models.ForeignKey(
        'accounts.AgentSFD',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflows_valides',
        help_text="Agent SFD ayant validé la demande"
    )

    # =============================================================================
    # SECTION 2: DONNÉES DE LA DEMANDE INITIALE (remplace DemandeAdhesion)
    # =============================================================================
    
    montant_mise = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1000'))],
        help_text="Montant de mise souhaité (FCFA)"
    )
    
    document_identite = models.FileField(
        upload_to='demandes/documents/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        null=True,
        blank=True,
        help_text="Document d'identité (CNI, Passeport, etc.)"
    )
    
    numero_telephone_paiement = models.CharField(
    max_length=15,
    null=True,        # ← Peut être NULL
    blank=True,       # ← Peut être vide
    help_text="Numéro de téléphone pour les paiements Mobile Money (saisi lors du paiement)"
)
    
    OPERATEUR_CHOICES = [
        ('mtn', 'MTN'),
        ('moov', 'Moov'),
        ('orange', 'Orange'),
    ]
    operateur_mobile_money = models.CharField(
        max_length=10,
        choices=OPERATEUR_CHOICES,
        null=True,        # ← Peut être NULL  
        blank=True,       # ← Peut être vide
        help_text="Opérateur Mobile Money choisi lors du paiement"
    )
    

    # =============================================================================
    # SECTION 3: ÉTAT DU WORKFLOW
    # =============================================================================
    
    statut_actuel = models.CharField(
        max_length=30,
        choices=STATUT_CHOICES,
        default='demande_soumise',
        help_text="Statut actuel du workflow"
    )
    
    etape_actuelle = models.CharField(
        max_length=20,
        choices=ETAPES_CHOICES,
        default='etape_1',
        help_text="Étape actuelle du processus"
    )

    # =============================================================================
    # SECTION 4: DATES IMPORTANTES
    # =============================================================================
    
    date_creation = models.DateTimeField(
        default=timezone.now,
        help_text="Date de soumission de la demande"
    )
    
    date_validation_agent = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de validation par l'agent"
    )
    
    date_paiement_frais = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de paiement des frais d'adhésion"
    )
    
    date_integration = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date d'intégration effective à la tontine"
    )
    
    
    # =============================================================================
    # SECTION 5: INFORMATIONS DE PAIEMENT
    # =============================================================================
    
    frais_adhesion_calcules = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Frais d'adhésion calculés automatiquement"
    )
    
    frais_adhesion_payes = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Montant des frais effectivement payés"
    )
    
    reference_paiement = models.CharField(
        max_length=100,
        blank=True,
        help_text="Référence du paiement Mobile Money"
    )
    
    transaction_mobile_money = models.ForeignKey(
        'payments.KKiaPayTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflows_adhesion',
        help_text="Transaction KKiaPay associée"
    )

    # =============================================================================
    # SECTION 6: NOTIFICATIONS ET COMMUNICATION
    # =============================================================================
    
    email_confirmation_envoye = models.BooleanField(
        default=False,
        help_text="Email de confirmation envoyé au client"
    )
    
    
    nombre_rappels_paiement = models.PositiveIntegerField(
        default=0,
        help_text="Nombre de rappels de paiement envoyés"
    )

    # =============================================================================
    # SECTION 7: MÉTADONNÉES ET COMMENTAIRES
    # =============================================================================
    
    commentaires_agent = models.TextField(
        blank=True,
        help_text="Commentaires de l'agent lors de la validation"
    )
    
    raison_rejet = models.TextField(
        blank=True,
        help_text="Raison du rejet de la demande"
    )
    
    metadata = models.JSONField(
        null=True,
        blank=True,
        help_text="Métadonnées additionnelles (tokens, API responses, etc.)"
    )
    
    date_modification = models.DateTimeField(
        auto_now=True,
        help_text="Date de dernière modification"
    )

    class Meta:
        verbose_name = "Workflow d'adhésion"
        verbose_name_plural = "Workflows d'adhésion"
        ordering = ['-date_creation']
        db_table = 'tontines_workflow_adhesion_unifie'
        
        # Index pour améliorer les performances
        indexes = [
            models.Index(fields=['client', 'statut_actuel']),
            models.Index(fields=['tontine', 'statut_actuel']),
            models.Index(fields=['date_creation']),
            models.Index(fields=['etape_actuelle', 'statut_actuel']),
        ]

    def __str__(self):
        return f"Workflow {self.client.nom_complet} → {self.tontine.nom} ({self.get_statut_actuel_display()})"

    def clean(self):
        """Validation des données du workflow"""
        super().clean()
        
        # Vérifier que le montant de mise respecte les limites de la tontine
        if self.tontine and self.montant_mise:
            if self.montant_mise < self.tontine.mise_min:
                raise ValidationError(f"Le montant de mise doit être au moins {self.tontine.mise_min} FCFA")
            if self.montant_mise > self.tontine.mise_max:
                raise ValidationError(f"Le montant de mise ne peut dépasser {self.tontine.mise_max} FCFA")
        
        # Vérifier la cohérence entre statut et étape
        coherence_map = {
            'demande_soumise': 'etape_1',
            'validee_agent': 'etape_2',
            'en_cours_paiement': 'etape_2',
            'paiement_effectue': 'etape_3',
            'adherent': 'etape_3',
        }
        
        if self.statut_actuel in coherence_map:
            if self.etape_actuelle != coherence_map[self.statut_actuel]:
                raise ValidationError(f"Incohérence entre statut '{self.statut_actuel}' et étape '{self.etape_actuelle}'")

    def save(self, *args, **kwargs):
        """Override save pour utiliser uniquement les frais d'adhésion définis dans la tontine"""
        if self.tontine:
            # CORRECTION : fraisAdhesion au lieu de frais_adhesion
            self.frais_adhesion_calcules = self.tontine.fraisAdhesion
        # Définir la date d'expiration si pas encore définie (7 jours après validation agent)
        if hasattr(self, 'statut_actuel') and self.statut_actuel == 'validee_agent' and not getattr(self, 'date_expiration', None):
            from datetime import timedelta
            self.date_expiration = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    # =============================================================================
    # MÉTHODES MÉTIER - ACTIONS DU WORKFLOW
    # =========================================c====================================

    @classmethod
    def creer_nouvelle_demande(cls, client, tontine, montant_mise, numero_telephone, operateur='mtn', document=None):
        """
        POINT D'ENTRÉE PRINCIPAL : Créer une nouvelle demande d'adhésion.
        
        Args:
            client: Instance Client
            tontine: Instance Tontine
            montant_mise: Decimal - Montant de la mise
            document: File - Document d'identité (optionnel)
        
        Returns:
            WorkflowAdhesion: Instance créée
        """
        workflow = cls.objects.create(
            client=client,
            tontine=tontine,
            montant_mise=montant_mise,
            document_identite=document,
            statut_actuel='demande_soumise',
            etape_actuelle='etape_1'
        )
        
        logger.info(f"Nouvelle demande d'adhésion créée : {workflow.id}")
        return workflow

    def valider_par_agent(self, agent, commentaires=""):
        """Valide la demande par un agent SFD"""
        if self.statut_actuel != 'demande_soumise':
            raise ValidationError("La demande doit être en statut 'demande_soumise' pour être validée")
        
        self.agent_validateur = agent
        self.date_validation_agent = timezone.now()
        self.statut_actuel = 'validee_agent'
        self.etape_actuelle = 'etape_2'
        self.commentaires_agent = commentaires
        self.save()
        
        logger.info(f"Demande {self.id} validée par l'agent {agent.nom_complet}")

    def initier_paiement(self):
        """Initie le paiement des frais d'adhésion via Mobile Money"""
        if self.statut_actuel != 'validee_agent':
            raise ValidationError("La demande doit être validée par un agent avant le paiement")
        from mobile_money.services_adhesion import AdhesionMobileMoneyService
        service = AdhesionMobileMoneyService()
        resultat = service.generer_paiement_adhesion(self, self.numero_telephone_paiement)
        if not resultat.get('success'):
            logger.error(f"Erreur lors de l'initiation du paiement Mobile Money: {resultat.get('error')}")
            raise ValidationError(resultat.get('error', 'Erreur lors de l’initiation du paiement.'))
        # Associer la transaction Mobile Money à l'adhésion
        from mobile_money.models import TransactionMobileMoney
        try:
            transaction = TransactionMobileMoney.objects.get(id=resultat['transaction_id'])
            self.transaction_mobile_money = transaction
        except Exception as e:
            logger.error(f"Impossible d'associer la transaction Mobile Money: {e}")
        self.statut_actuel = 'en_cours_paiement'
        self.save()
        logger.info(f"Paiement initié pour la demande {self.id}")
        return resultat

    def confirmer_paiement(self, montant_paye, reference_paiement, transaction_mm=None):
        """Confirme le paiement des frais d'adhésion via Mobile Money"""
        if self.statut_actuel not in ['validee_agent', 'en_cours_paiement']:
            raise ValidationError("Paiement non autorisé pour ce statut")
        from mobile_money.services_adhesion import AdhesionMobileMoneyService
        service = AdhesionMobileMoneyService()
        resultat = service.traiter_confirmation_paiement(reference_paiement, 'succes', {})
        if not resultat.get('success'):
            logger.error(f"Erreur lors de la confirmation du paiement Mobile Money: {resultat.get('error')}")
            raise ValidationError(resultat.get('error', 'Erreur lors de la confirmation du paiement.'))
        self.frais_adhesion_payes = montant_paye
        self.reference_paiement = reference_paiement
        if transaction_mm:
            self.transaction_mobile_money = transaction_mm
        self.date_paiement_frais = timezone.now()
        self.statut_actuel = 'paiement_effectue'
        self.save()
        # Passer automatiquement à l'étape suivante
        self.finaliser_adhesion()
        logger.info(f"Paiement confirmé pour la demande {self.id} : {montant_paye} FCFA")

    def finaliser_adhesion(self):
        """Finalise l'adhésion et crée le TontineParticipant"""
        if self.statut_actuel != 'paiement_effectue':
            raise ValidationError("Le paiement doit être effectué avant la finalisation")
          # Créer le participant à la tontine
        participant = TontineParticipant.objects.create(
            tontine=self.tontine,
            client=self.client,
            montantMise=self.montant_mise,
            statut='actif',
            dateAdhesion=timezone.now()
        )
        
        # Finaliser le workflow
        self.statut_actuel = 'adherent'
        self.etape_actuelle = 'etape_3'
        self.date_integration = timezone.now()
        self.save()
        
        logger.info(f"Adhésion finalisée pour {self.client.nom_complet} à la tontine {self.tontine.nom}")
        return participant

    def rejeter(self, raison, agent=None):
        """Rejette la demande d'adhésion"""
        self.statut_actuel = 'rejetee'
        self.raison_rejet = raison
        if agent:
            self.agent_validateur = agent
        self.save()
        
        logger.info(f"Demande {self.id} rejetée : {raison}")

   
    # =============================================================================
    # PROPRIÉTÉS UTILES
    # =============================================================================

    @property
    def peut_etre_validee(self):
        """Vérifie si la demande peut être validée par un agent"""
        return self.statut_actuel == 'demande_soumise'

    @property 
    def peut_payer_frais(self):
        """Vérifie si le client peut payer les frais d'adhésion"""
        return self.statut_actuel in ['validee_agent', 'en_cours_paiement']

    @property
    def est_complete(self):
        """Vérifie si le workflow est terminé avec succès"""
        return self.statut_actuel == 'adherent'

    @property
    def est_active(self):
        """Vérifie si la demande est encore active (pas rejetée/expirée)"""
        return self.statut_actuel not in ['rejetee', 'expiree']


    @property
    def prochaine_action_requise(self):
        """Détermine la prochaine action requise"""
        actions_map = {
            'demande_soumise': "Validation par un agent SFD",
            'validee_agent': "Paiement des frais d'adhésion via Mobile Money",
            'en_cours_paiement': "Confirmation du paiement Mobile Money",
            'paiement_effectue': "Intégration automatique à la tontine",
            'adherent': "Adhésion terminée - Vous êtes membre actif",
            'rejetee': "Demande rejetée - Contactez votre SFD",
            'expiree': "Demande expirée - Créez une nouvelle demande",
        }
        return actions_map.get(self.statut_actuel, "Action inconnue")


    @property
    def to_dict(self):
        """Retourne les données du workflow sous forme de dictionnaire, version à jour sans frais_adhesion_calcules."""
        # Récupération de l'URL du document d'identité
        doc_url = self.document_identite.url if self.document_identite else None
        # Affichage lisible de l'opérateur mobile money si possible
        operateur_display = None
        if self.operateur_mobile_money:
            try:
                operateur_display = self.get_operateur_mobile_money_display()
            except Exception:
                operateur_display = self.operateur_mobile_money
        return {
            'id': str(self.id),
            'client': {
                'id': str(self.client.id),
                'nom_complet': self.client.nom_complet,
                'email': self.client.email,
                'telephone': self.client.telephone,
            },
            'tontine': {
                'id': str(self.tontine.id),
                'nom': self.tontine.nom,
                'mise_min': str(getattr(self.tontine, 'mise_min', getattr(self.tontine, 'montantMinMise', ''))),
                'mise_max': str(getattr(self.tontine, 'mise_max', getattr(self.tontine, 'montantMaxMise', ''))),
                'frais_adhesion': str(self.tontine.fraisAdhesion),
            },
            'demande': {
                'montant_mise': str(self.montant_mise),
                'numero_telephone_paiement': self.numero_telephone_paiement,
                'operateur_mobile_money': operateur_display,
                'document_identite': doc_url,
            },
            'workflow': {
                'statut_actuel': self.statut_actuel,
                'etape_actuelle': self.etape_actuelle,
                'progression': getattr(self, 'progression_pourcentage', None),
                'prochaine_action': self.prochaine_action_requise,
            },
            'dates': {
                'creation': self.date_creation.isoformat(),
                'validation_agent': self.date_validation_agent.isoformat() if self.date_validation_agent else None,
                'paiement_frais': self.date_paiement_frais.isoformat() if self.date_paiement_frais else None,
                'integration': self.date_integration.isoformat() if self.date_integration else None,
                'expiration': self.date_expiration.isoformat() if hasattr(self, 'date_expiration') and self.date_expiration else None,
            },
            'agent_validateur': {
                'id': str(self.agent_validateur.id),
                'nom_complet': self.agent_validateur.nom_complet,
            } if self.agent_validateur else None,
            'paiement': {
                'frais_payes': str(self.frais_adhesion_payes) if self.frais_adhesion_payes else None,
                'reference': self.reference_paiement,
            },
            'commentaires': {
                'agent': self.commentaires_agent,
                'raison_rejet': self.raison_rejet,
                'notes_internes': getattr(self, 'notes_internes', None),
            }
        }

class Cotisation(models.Model):
    """
    Modèle représentant une cotisation d'un client à une tontine.
    Chaque cotisation correspond au paiement d'une mise quotidienne.
    """
    
    class StatutCotisationChoices(models.TextChoices):
        PENDING = 'pending', 'En attente'
        CONFIRMEE = 'confirmee', 'Confirmée'
        REJETEE = 'rejetee', 'Rejetée'
    
    id = models.AutoField(
        primary_key=True,
        help_text="Identifiant unique de la cotisation"
    )
    
    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1.00'))],
        help_text="Montant de la cotisation en FCFA"
    )
    
    date_cotisation = models.DateTimeField(
        auto_now_add=True,
        help_text="Date et heure de la cotisation"
    )
    
    numero_transaction = models.CharField(
        max_length=255,
        unique=True,
        help_text="Numéro de transaction Mobile Money"
    )
    
    statut = models.CharField(
        max_length=20,
        choices=StatutCotisationChoices.choices,
        default=StatutCotisationChoices.PENDING,
        help_text="Statut de la cotisation"
    )
    
    tontine = models.ForeignKey(
        'Tontine',
        on_delete=models.CASCADE,
        related_name='cotisations',
        help_text="Tontine concernée par cette cotisation"
    )
    
    client = models.ForeignKey(
        'accounts.Client',
        on_delete=models.CASCADE,
        related_name='cotisations',
        help_text="Client ayant effectué la cotisation"
    )
    
    # Référence vers la transaction Mobile Money
    transaction_mobile_money = models.ForeignKey(
        'mobile_money.TransactionMobileMoney',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cotisations_associees',
        help_text="Transaction Mobile Money associée"
    )
    
    class Meta:
        verbose_name = "Cotisation"
        verbose_name_plural = "Cotisations"
        ordering = ['-date_cotisation']
        db_table = 'tontines_cotisation'
        
        # Index pour améliorer les performances
        indexes = [
            models.Index(fields=['tontine', 'client']),
            models.Index(fields=['date_cotisation']),
            models.Index(fields=['statut']),
            models.Index(fields=['numero_transaction']),
        ]
    
    def __str__(self):
        return f"Cotisation {self.client.nom_complet} - {self.tontine.nom} - {self.montant} FCFA"
    
    def clean(self):
        """Validation des données de cotisation"""
        super().clean()
        
        # Vérifier que le montant respecte les limites de la tontine
        if self.tontine and self.montant:
            if not self.tontine.verifierLimitesMise(self.montant):
                raise ValidationError(
                    f"Le montant doit être compris entre {self.tontine.montantMinMise} "
                    f"et {self.tontine.montantMaxMise} FCFA"
                )
        
        # Vérifier que le client est participant à la tontine
        if self.tontine and self.client:
            if not TontineParticipant.objects.filter(
                tontine=self.tontine,
                client=self.client,
                statut='actif'
            ).exists():
                raise ValidationError("Le client doit être participant actif de cette tontine")

class Retrait(models.Model):
    """
    Modèle représentant une demande de retrait d'un client dans une tontine.
    Les retraits doivent être validés par un agent SFD.
    """
    
    class StatutRetraitChoices(models.TextChoices):
        PENDING = 'pending', 'En attente'
        APPROVED = 'approved', 'Approuvé'
        REJECTED = 'rejected', 'Rejeté'
        CONFIRMEE = 'confirmee', 'Confirmé'
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identifiant unique du retrait"
    )
    
    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1.00'))],
        help_text="Montant demandé pour le retrait en FCFA"
    )
    
    date_demande_retrait = models.DateTimeField(
        auto_now_add=True,
        help_text="Date et heure de la demande de retrait"
    )
    
    date_validation_retrait = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date et heure de validation du retrait par l'agent"
    )
    
    statut = models.CharField(
        max_length=20,
        choices=StatutRetraitChoices.choices,
        default=StatutRetraitChoices.PENDING,
        help_text="Statut de la demande de retrait"
    )
    
    tontine = models.ForeignKey(
        'Tontine',
        on_delete=models.CASCADE,
        related_name='retraits',
        help_text="Tontine concernée par ce retrait"
    )
    
    client = models.ForeignKey(
        'accounts.Client',
        on_delete=models.CASCADE,
        related_name='retraits',
        help_text="Client demandant le retrait"
    )
    
    # Agent qui valide/rejette le retrait
    agent_validateur = models.ForeignKey(
        'accounts.AgentSFD',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='retraits_valides',
        help_text="Agent SFD ayant validé/rejeté le retrait"
    )
    
    # Commentaires et métadonnées
    commentaires_agent = models.TextField(
        blank=True,
        help_text="Commentaires de l'agent lors de la validation"
    )
    
    raison_rejet = models.TextField(
        blank=True,
        help_text="Raison du rejet du retrait"
    )
    
    # Référence vers la transaction Mobile Money (pour le versement)
    transaction_mobile_money = models.ForeignKey(
        'mobile_money.TransactionMobileMoney',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='retraits_associes',
        help_text="Transaction Mobile Money de versement"
    )
    
    class Meta:
        verbose_name = "Retrait"
        verbose_name_plural = "Retraits"
        ordering = ['-date_demande_retrait']
        db_table = 'tontines_retrait'
        
        # Index pour améliorer les performances
        indexes = [
            models.Index(fields=['tontine', 'client']),
            models.Index(fields=['date_demande_retrait']),
            models.Index(fields=['statut']),
            models.Index(fields=['agent_validateur']),
        ]
    
    def __str__(self):
        return f"Retrait {self.client.nom_complet} - {self.tontine.nom} - {self.montant} FCFA ({self.get_statut_display()})"
    
    def clean(self):
        """Validation des données de retrait"""
        super().clean()
        
        # Vérifier que le client est participant à la tontine
        if self.tontine and self.client:
            if not TontineParticipant.objects.filter(
                tontine=self.tontine,
                client=self.client,
                statut='actif'
            ).exists():
                raise ValidationError("Le client doit être participant actif de cette tontine")
        
        # Vérifier que le client a un solde suffisant
        if self.tontine and self.client and self.montant:
            solde_client = self.tontine.calculerSoldeClient(self.client.id)
            if self.montant > solde_client:
                raise ValidationError(
                    f"Montant insuffisant. Solde disponible: {solde_client} FCFA"
                )
    
    def approuver(self, agent, commentaires=""):
        """Approuve la demande de retrait"""
        if self.statut != self.StatutRetraitChoices.PENDING:
            raise ValidationError("Seules les demandes en attente peuvent être approuvées")
        
        self.statut = self.StatutRetraitChoices.APPROVED
        self.agent_validateur = agent
        self.date_validation_retrait = timezone.now()
        self.commentaires_agent = commentaires
        self.save()
    
    def rejeter(self, agent, raison):
        """Rejette la demande de retrait"""
        if self.statut != self.StatutRetraitChoices.PENDING:
            raise ValidationError("Seules les demandes en attente peuvent être rejetées")
        
        self.statut = self.StatutRetraitChoices.REJECTED
        self.agent_validateur = agent
        self.date_validation_retrait = timezone.now()
        self.raison_rejet = raison
        self.save()
    
    def confirmer(self, transaction_mm=None):
        """Confirme le retrait après versement Mobile Money"""
        if self.statut != self.StatutRetraitChoices.APPROVED:
            raise ValidationError("Le retrait doit être approuvé avant confirmation")
        
        self.statut = self.StatutRetraitChoices.CONFIRMEE
        if transaction_mm:
            self.transaction_mobile_money = transaction_mm
        self.save()


class SoldeTontine(models.Model):
    """
    Modèle pour gérer le solde de chaque client dans chaque tontine.
    Permet de tracer les montants cotisés hors commissions SFD.
    """
    
    client = models.ForeignKey(
        'accounts.Client',
        on_delete=models.CASCADE,
        related_name='soldes_tontines',
        help_text="Client propriétaire du solde"
    )
    
    tontine = models.ForeignKey(
        Tontine,
        on_delete=models.CASCADE,
        related_name='soldes_clients',
        help_text="Tontine concernée"
    )
    
    solde = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Solde du client dans cette tontine (hors commissions SFD)"
    )
    
    date_creation = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de création du solde"
    )
    
    date_modification = models.DateTimeField(
        auto_now=True,
        help_text="Date de dernière modification"
    )
    
    class Meta:
        unique_together = ('client', 'tontine')
        verbose_name = "Solde Tontine"
        verbose_name_plural = "Soldes Tontines"
        db_table = 'tontines_solde_tontine'
        indexes = [
            models.Index(fields=['client', 'tontine']),
        ]
    
    def __str__(self):
        return f"{self.client.nom_complet} - {self.tontine.nom} : {self.solde} FCFA"


def default_mises_carnet():
    """Fonction pour générer la liste par défaut des mises (31 False)"""
    return [False] * 31

class CarnetCotisation(models.Model):
    """
    Modèle pour gérer le carnet de cotisation 31 jours de chaque client.
    Utilise un JSONField pour stocker les 31 cases (True/False).
    """
    client = models.ForeignKey(
        'accounts.Client',
        on_delete=models.CASCADE,
        related_name='carnets_cotisation',
        help_text="Client propriétaire du carnet"
    )
    
    tontine = models.ForeignKey(
        Tontine,
        on_delete=models.CASCADE,
        related_name='carnets_cotisation',
        help_text="Tontine concernée"
    )
    
    cycle_debut = models.DateField(
        help_text="Date de début du cycle 31 jours"
    )
    
    mises_cochees = models.JSONField(
        default=default_mises_carnet,
        help_text="Liste de 31 booleans représentant les mises cochées (jour 1 à 31)"
    )
    
    date_creation = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de création du carnet"
    )
    
    date_modification = models.DateTimeField(
        auto_now=True,
        help_text="Date de dernière modification"
    )
    
    class Meta:
        unique_together = ('client', 'tontine', 'cycle_debut')
        verbose_name = "Carnet Cotisation"
        verbose_name_plural = "Carnets Cotisation"
        db_table = 'tontines_carnet_cotisation'
        indexes = [
            models.Index(fields=['client', 'tontine', 'cycle_debut']),
        ]
    
    def __str__(self):
        mises_cochees_count = sum(self.mises_cochees)
        return f"{self.client.nom_complet} - {self.tontine.nom} - Cycle {self.cycle_debut} ({mises_cochees_count}/31)"
    
    def cocher_mise(self, jour):
        """
        Coche une mise pour un jour donné (1-31).
        
        Args:
            jour (int): Numéro du jour (1 à 31)
        """
        if 1 <= jour <= 31:
            self.mises_cochees[jour - 1] = True
            self.save()
    
    def est_complete(self):
        """Vérifie si le carnet est complet (31 mises cochées)."""
        return sum(self.mises_cochees) == 31
    
    def nombre_mises_cochees(self):
        """Retourne le nombre de mises cochées."""
        return sum(self.mises_cochees)
    
    def prochaine_mise_libre(self):
        """Retourne le numéro du prochain jour libre (1-31) ou None si complet."""
        for i, coche in enumerate(self.mises_cochees):
            if not coche:
                return i + 1
        return None
