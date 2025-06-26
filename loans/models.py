"""
MODÈLES DJANGO POUR LE MODULE PRÊTS - TONTIFLEX

Ce module implémente le système de prêts avec workflow obligatoire:
1. Vérification éligibilité (compte épargne > 3 mois)
2. Demande complète avec documents PDF
3. Traitement Superviseur (conditions + transfert obligatoire)
4. Validation finale Admin obligatoire
5. Décaissement + remboursements Mobile Money
6. Calculs automatiques échéances et pénalités

Workflow: Client → Superviseur → Admin → Décaissement → Remboursements
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
import uuid
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class LoanApplication(models.Model):
    """
    Demande de prêt complète avec workflow obligatoire Superviseur → Admin.
    
    Workflow TontiFlex:
    1. soumis: Client remplit formulaire complet
    2. en_cours_examen: Superviseur examine + définit conditions
    3. transfere_admin: Transfert obligatoire à Admin
    4. accorde: Admin valide définitivement
    5. decaisse: Prêt retiré physiquement
    6. en_remboursement: Remboursements en cours
    7. solde: Prêt remboursé intégralement
    8. rejete: Rejet à n'importe quelle étape
    """
    
    class StatutChoices(models.TextChoices):
        SOUMIS = 'soumis', 'Soumis'
        EN_COURS_EXAMEN = 'en_cours_examen', 'En cours d\'examen'
        TRANSFERE_ADMIN = 'transfere_admin', 'Transféré à Admin'
        ACCORDE = 'accorde', 'Accordé'
        DECAISSE = 'decaisse', 'Décaissé'
        EN_REMBOURSEMENT = 'en_remboursement', 'En remboursement'
        SOLDE = 'solde', 'Soldé'
        REJETE = 'rejete', 'Rejeté'
    
    class TypePretChoices(models.TextChoices):
        CONSOMMATION = 'consommation', 'Prêt à la consommation'
        IMMOBILIER = 'immobilier', 'Prêt immobilier'
        PROFESSIONNEL = 'professionnel', 'Prêt professionnel'
        URGENCE = 'urgence', 'Prêt d\'urgence'
    
    class SituationFamilialeChoices(models.TextChoices):
        CELIBATAIRE = 'celibataire', 'Célibataire'
        MARIE = 'marie', 'Marié(e)'
        DIVORCE = 'divorce', 'Divorcé(e)'
        VEUF = 'veuf', 'Veuf/Veuve'
        UNION_LIBRE = 'union_libre', 'Union libre'
    
    class TypeGarantieChoices(models.TextChoices):
        BIEN_IMMOBILIER = 'bien_immobilier', 'Bien immobilier'
        GARANT_PHYSIQUE = 'garant_physique', 'Garant physique'
        DEPOT_GARANTIE = 'depot_garantie', 'Dépôt de garantie'
        AUCUNE = 'aucune', 'Aucune garantie'
    
    # =============================================================================
    # SECTION 1: IDENTIFIANTS ET RELATIONS
    # =============================================================================
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identifiant unique de la demande de prêt"
    )
    
    client = models.ForeignKey(
        'accounts.Client',
        on_delete=models.CASCADE,
        related_name='demandes_prets',
        help_text="Client demandeur du prêt"
    )
    
    superviseur_examinateur = models.ForeignKey(
        'accounts.SuperviseurSFD',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='demandes_examinees',
        help_text="Superviseur SFD ayant examiné la demande"
    )
    
    admin_validateur = models.ForeignKey(
        'accounts.AdministrateurSFD',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prets_valides',
        help_text="Admin SFD ayant validé définitivement"
    )
    
    # =============================================================================
    # SECTION 2: STATUT ET WORKFLOW
    # =============================================================================
    
    statut = models.CharField(
        max_length=20,
        choices=StatutChoices.choices,
        default=StatutChoices.SOUMIS,
        help_text="Statut actuel de la demande dans le workflow"
    )
    
    date_soumission = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de soumission initiale de la demande"
    )
    
    date_examen_superviseur = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date d'examen par le superviseur"
    )
    
    date_transfert_admin = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de transfert obligatoire à l'admin"
    )
    
    date_validation_admin = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de validation finale par l'admin"
    )
    
    date_decaissement = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de décaissement physique du prêt"
    )
    
    # =============================================================================
    # SECTION 3: INFORMATIONS PERSONNELLES DÉTAILLÉES
    # =============================================================================
    
    nom = models.CharField(
        max_length=100,
        help_text="Nom de famille (peut différer du compte client)"
    )
    
    prenom = models.CharField(
        max_length=100,
        help_text="Prénom (peut différer du compte client)"
    )
    
    date_naissance = models.DateField(
        help_text="Date de naissance du demandeur"
    )
    
    adresse_domicile = models.TextField(
        help_text="Adresse complète du domicile"
    )
    
    adresse_bureau = models.TextField(
        blank=True,
        help_text="Adresse du lieu de travail/bureau"
    )
    
    situation_familiale = models.CharField(
        max_length=20,
        choices=SituationFamilialeChoices.choices,
        help_text="Situation familiale du demandeur"
    )
    
    telephone = models.CharField(
        max_length=15,
        help_text="Numéro de téléphone principal"
    )
    
    email = models.EmailField(
        help_text="Adresse email du demandeur"
    )
    
    situation_professionnelle = models.TextField(
        help_text="Description détaillée: emploi, entreprise, fonction"
    )
    
    justificatif_identite = models.CharField(
        max_length=50,
        help_text="Type de justificatif d'identité fourni"
    )
    
    # =============================================================================
    # SECTION 4: SITUATION FINANCIÈRE
    # =============================================================================
    
    revenu_mensuel = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Revenu mensuel total en FCFA"
    )
    
    charges_mensuelles = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Charges mensuelles totales en FCFA"
    )
    
    historique_prets_anterieurs = models.TextField(
        blank=True,
        help_text="Historique des prêts antérieurs et leur statut"
    )
    
    plan_affaires = models.TextField(
        blank=True,
        help_text="Plan d'affaires pour prêts professionnels (optionnel)"
    )
    
    # =============================================================================
    # SECTION 5: DÉTAILS DU PRÊT DEMANDÉ
    # =============================================================================
    
    montant_souhaite = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('10000.00'))],
        help_text="Montant du prêt souhaité en FCFA"
    )
    
    duree_pret = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(60)],
        help_text="Durée du prêt en mois (1-60)"
    )
    
    type_pret = models.CharField(
        max_length=20,
        choices=TypePretChoices.choices,
        help_text="Type de prêt demandé"
    )
    
    objet_pret = models.TextField(
        help_text="Description détaillée de l'objet du prêt"
    )
    
    # =============================================================================
    # SECTION 6: GARANTIES
    # =============================================================================
    
    type_garantie = models.CharField(
        max_length=20,
        choices=TypeGarantieChoices.choices,
        help_text="Type de garantie proposée"
    )
    
    details_garantie = models.TextField(
        blank=True,
        help_text="Détails de la garantie (description, valeur, etc.)"
    )
    
    signature_caution = models.BooleanField(
        default=False,
        help_text="Signature de caution fournie si exigée"
    )
    
    # =============================================================================
    # SECTION 7: CONSENTEMENTS
    # =============================================================================
    
    signature_collecte_donnees = models.BooleanField(
        default=False,
        help_text="Consentement pour la collecte et traitement des données"
    )
    
    # =============================================================================
    # SECTION 8: DOCUMENTS CONSOLIDÉS
    # =============================================================================
    
    document_complet = models.FileField(
        upload_to='loans/documents/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        help_text="Document PDF consolidé avec toutes les pièces justificatives"
    )
    
    # =============================================================================
    # SECTION 9: COMMENTAIRES ET HISTORIQUE
    # =============================================================================
    
    commentaires_superviseur = models.TextField(
        blank=True,
        help_text="Commentaires du superviseur lors de l'examen"
    )
    
    commentaires_admin = models.TextField(
        blank=True,
        help_text="Commentaires de l'admin lors de la validation"
    )
    
    raison_rejet = models.TextField(
        blank=True,
        help_text="Raison du rejet si demande refusée"
    )
    
    score_fiabilite = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Score de fiabilité calculé automatiquement (0-100)"
    )
    
    # =============================================================================
    # SECTION 10: MÉTADONNÉES
    # =============================================================================
    
    date_creation = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de création de l'enregistrement"
    )
    
    date_modification = models.DateTimeField(
        auto_now=True,
        help_text="Date de dernière modification"
    )
    
    class Meta:
        verbose_name = "Demande de Prêt"
        verbose_name_plural = "Demandes de Prêt"
        ordering = ['-date_soumission']
        db_table = 'loans_application'
        
        indexes = [
            models.Index(fields=['client', 'statut']),
            models.Index(fields=['date_soumission']),
            models.Index(fields=['superviseur_examinateur']),
            models.Index(fields=['admin_validateur']),
        ]
    
    def __str__(self):
        return f"Demande #{self.id.hex[:8]} - {self.client.nom_complet} - {self.montant_souhaite} FCFA"
    
    def clean(self):
        """Validation des données de la demande"""
        super().clean()
        
        # Validation cohérence financière
        if self.revenu_mensuel and self.charges_mensuelles:
            if self.charges_mensuelles >= self.revenu_mensuel:
                raise ValidationError("Les charges ne peuvent pas être supérieures ou égales aux revenus")
        
        # Validation âge minimum (18 ans)
        if self.date_naissance:
            age = (timezone.now().date() - self.date_naissance).days / 365.25
            if age < 18:
                raise ValidationError("Le demandeur doit être majeur (18 ans minimum)")
        
        # Validation consentement obligatoire
        if not self.signature_collecte_donnees:
            raise ValidationError("Le consentement pour la collecte des données est obligatoire")
    
    def save(self, *args, **kwargs):
        """Override save pour calculs automatiques"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    # =============================================================================
    # MÉTHODES MÉTIER - WORKFLOW
    # =============================================================================
    
    @classmethod
    def verifier_eligibilite(cls, client):
        """
        Vérifie l'éligibilité d'un client pour un prêt.
        Règle: Compte épargne actif depuis plus de 3 mois obligatoire.
        """
        try:
            compte_epargne = client.compte_epargne
            
            # Vérifier que le compte existe et est actif
            if compte_epargne.statut != 'actif':
                return {
                    'eligible': False,
                    'raison': 'Votre compte épargne n\'est pas actif'
                }
            
            # Vérifier ancienneté > 3 mois
            date_limite = timezone.now() - timedelta(days=90)  # 3 mois = 90 jours
            if compte_epargne.date_activation > date_limite:
                anciennete_jours = (timezone.now() - compte_epargne.date_activation).days
                return {
                    'eligible': False,
                    'raison': f'Votre compte épargne doit être actif depuis plus de 3 mois. '
                             f'Ancienneté actuelle: {anciennete_jours} jours'
                }
            
            return {'eligible': True, 'raison': 'Éligible pour une demande de prêt'}
            
        except Exception as e:
            return {
                'eligible': False,
                'raison': 'Aucun compte épargne trouvé. Vous devez d\'abord ouvrir un compte épargne.'
            }
    
    def calculer_score_fiabilite(self):
        """
        Calcule automatiquement le score de fiabilité du client.
        Basé sur l'historique des cotisations, dépôts, retraits.
        """
        try:
            client = self.client
            score = Decimal('50.00')  # Score de base
            
            # Bonus pour compte épargne ancien (max 20 points)
            if hasattr(client, 'compte_epargne'):
                anciennete_mois = (timezone.now() - client.compte_epargne.date_activation).days / 30
                score += min(Decimal('20.00'), Decimal(str(anciennete_mois * 2)))
            
            # Bonus pour participation aux tontines (max 15 points)
            tontines_actives = client.tontines_participees.filter(statut='actif').count()
            score += min(Decimal('15.00'), Decimal(str(tontines_actives * 5)))
            
            # Bonus pour régularité des cotisations (max 15 points)
            # À implémenter selon la logique métier existante
            
            self.score_fiabilite = min(score, Decimal('100.00'))
            self.save(update_fields=['score_fiabilite'])
            
            return self.score_fiabilite
            
        except Exception as e:
            logger.error(f"Erreur calcul score fiabilité pour demande {self.id}: {e}")
            return Decimal('0.00')
    
    def examiner_par_superviseur(self, superviseur, commentaires=""):
        """Passage de l'examen par le superviseur"""
        if self.statut != self.StatutChoices.SOUMIS:
            raise ValidationError("Seules les demandes soumises peuvent être examinées")
        
        self.statut = self.StatutChoices.EN_COURS_EXAMEN
        self.superviseur_examinateur = superviseur
        self.date_examen_superviseur = timezone.now()
        self.commentaires_superviseur = commentaires
        
        # Calcul automatique du score de fiabilité
        self.calculer_score_fiabilite()
        
        self.save()
        logger.info(f"Demande {self.id} examinée par superviseur {superviseur}")
    
    def transferer_a_admin(self, superviseur):
        """Transfert obligatoire à l'admin après définition des conditions"""
        if self.statut != self.StatutChoices.EN_COURS_EXAMEN:
            raise ValidationError("La demande doit être en cours d'examen pour être transférée")
        
        if self.superviseur_examinateur != superviseur:
            raise ValidationError("Seul le superviseur examinateur peut transférer la demande")
        
        # Vérifier que les conditions de remboursement sont définies
        if not hasattr(self, 'conditions_remboursement'):
            raise ValidationError("Les conditions de remboursement doivent être définies avant le transfert")
        
        self.statut = self.StatutChoices.TRANSFERE_ADMIN
        self.date_transfert_admin = timezone.now()
        self.save()
        
        logger.info(f"Demande {self.id} transférée à l'admin par superviseur {superviseur}")
    
    def valider_par_admin(self, admin, commentaires=""):
        """Validation finale obligatoire par l'admin"""
        if self.statut != self.StatutChoices.TRANSFERE_ADMIN:
            raise ValidationError("Seules les demandes transférées peuvent être validées par l'admin")
        
        self.statut = self.StatutChoices.ACCORDE
        self.admin_validateur = admin
        self.date_validation_admin = timezone.now()
        self.commentaires_admin = commentaires
        self.save()
        
        # Créer automatiquement l'objet Loan
        loan = Loan.objects.create(
            demande=self,
            client=self.client,
            montant_accorde=self.montant_souhaite,
            statut='accorde'
        )
        
        logger.info(f"Demande {self.id} accordée par admin {admin}")
        return loan
    
    def rejeter(self, utilisateur, raison):
        """Rejeter la demande à n'importe quelle étape"""
        if self.statut in [self.StatutChoices.ACCORDE, self.StatutChoices.DECAISSE, 
                          self.StatutChoices.EN_REMBOURSEMENT, self.StatutChoices.SOLDE]:
            raise ValidationError("Impossible de rejeter un prêt déjà accordé ou en cours")
        
        self.statut = self.StatutChoices.REJETE
        self.raison_rejet = raison
        self.save()
        
        logger.info(f"Demande {self.id} rejetée par {utilisateur}: {raison}")
    
    # =============================================================================
    # PROPRIÉTÉS UTILES
    # =============================================================================
    
    @property
    def peut_etre_examinee(self):
        """Vérifie si la demande peut être examinée par un superviseur"""
        return self.statut == self.StatutChoices.SOUMIS
    
    @property
    def peut_etre_transferee(self):
        """Vérifie si la demande peut être transférée à l'admin"""
        return (self.statut == self.StatutChoices.EN_COURS_EXAMEN and 
                hasattr(self, 'conditions_remboursement'))
    
    @property
    def peut_etre_validee(self):
        """Vérifie si la demande peut être validée par l'admin"""
        return self.statut == self.StatutChoices.TRANSFERE_ADMIN
    
    @property
    def ratio_endettement(self):
        """Calcule le ratio d'endettement"""
        if self.revenu_mensuel and self.revenu_mensuel > 0:
            return (self.charges_mensuelles / self.revenu_mensuel) * 100
        return 0
    
    @property
    def prochaine_action(self):
        """Détermine la prochaine action requise"""
        actions = {
            self.StatutChoices.SOUMIS: "Examen par superviseur SFD",
            self.StatutChoices.EN_COURS_EXAMEN: "Définition conditions + transfert admin",
            self.StatutChoices.TRANSFERE_ADMIN: "Validation finale par admin SFD",
            self.StatutChoices.ACCORDE: "En attente de décaissement",
            self.StatutChoices.DECAISSE: "Remboursements en cours",
            self.StatutChoices.EN_REMBOURSEMENT: "Suivi des remboursements",
            self.StatutChoices.SOLDE: "Prêt terminé",
            self.StatutChoices.REJETE: "Demande rejetée"
        }
        return actions.get(self.statut, "Action inconnue")


class LoanTerms(models.Model):
    """
    Conditions de remboursement définies par le superviseur.
    Obligatoire avant le transfert à l'admin.
    """
    
    demande = models.OneToOneField(
        'LoanApplication',
        on_delete=models.CASCADE,
        related_name='conditions_remboursement',
        help_text="Demande de prêt associée"
    )
    
    taux_interet_annuel = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('50.00'))],
        help_text="Taux d'intérêt annuel en pourcentage"
    )
    
    jour_echeance_mensuelle = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text="Jour du mois pour les échéances (1-31)"
    )
    
    taux_penalite_quotidien = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('10.00'))],
        help_text="Taux de pénalité par jour de retard en pourcentage"
    )
    
    montant_mensualite = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Montant de la mensualité calculée"
    )
    
    date_premiere_echeance = models.DateField(
        help_text="Date de la première échéance"
    )
    
    superviseur_definisseur = models.ForeignKey(
        'accounts.SuperviseurSFD',
        on_delete=models.CASCADE,
        related_name='conditions_definies',
        help_text="Superviseur ayant défini les conditions"
    )
    
    date_creation = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de définition des conditions"
    )
    
    class Meta:
        verbose_name = "Conditions de Remboursement"
        verbose_name_plural = "Conditions de Remboursement"
        db_table = 'loans_terms'
    
    def __str__(self):
        return f"Conditions - {self.demande.client.nom_complet} - {self.taux_interet_annuel}%"
    
    def save(self, *args, **kwargs):
        """Calcul automatique de la mensualité"""
        if not self.montant_mensualite:
            self.montant_mensualite = self.calculer_mensualite()
        
        if not self.date_premiere_echeance:
            self.date_premiere_echeance = self.calculer_premiere_echeance()
        
        super().save(*args, **kwargs)
    
    def calculer_mensualite(self):
        """Calcule la mensualité avec intérêts"""
        montant = self.demande.montant_souhaite
        duree_mois = self.demande.duree_pret
        taux_mensuel = self.taux_interet_annuel / Decimal('12') / Decimal('100')
        
        if taux_mensuel == 0:
            return montant / duree_mois
        
        # Formule de calcul de mensualité
        coefficient = (taux_mensuel * (1 + taux_mensuel) ** duree_mois) / \
                     ((1 + taux_mensuel) ** duree_mois - 1)
        
        return montant * coefficient
    
    def calculer_premiere_echeance(self):
        """Calcule la date de première échéance"""
        today = timezone.now().date()
        
        # Si le jour choisi est déjà passé ce mois, prendre le mois suivant
        try:
            premiere_echeance = today.replace(day=self.jour_echeance_mensuelle)
            if premiere_echeance <= today:
                # Ajouter un mois
                if today.month == 12:
                    premiere_echeance = premiere_echeance.replace(year=today.year + 1, month=1)
                else:
                    premiere_echeance = premiere_echeance.replace(month=today.month + 1)
        except ValueError:
            # Cas où le jour n'existe pas dans le mois (ex: 31 février)
            if today.month == 12:
                premiere_echeance = today.replace(year=today.year + 1, month=1, day=min(self.jour_echeance_mensuelle, 28))
            else:
                premiere_echeance = today.replace(month=today.month + 1, day=min(self.jour_echeance_mensuelle, 28))
        
        return premiere_echeance


class Loan(models.Model):
    """
    Prêt accordé avec suivi du décaissement et des remboursements.
    Créé automatiquement après validation admin.
    """
    
    class StatutChoices(models.TextChoices):
        ACCORDE = 'accorde', 'Accordé'
        EN_ATTENTE_DECAISSEMENT = 'en_attente_decaissement', 'En attente décaissement'
        DECAISSE = 'decaisse', 'Décaissé'
        EN_REMBOURSEMENT = 'en_remboursement', 'En remboursement'
        SOLDE = 'solde', 'Soldé'
        EN_DEFAUT = 'en_defaut', 'En défaut'
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identifiant unique du prêt"
    )
    
    demande = models.OneToOneField(
        'LoanApplication',
        on_delete=models.CASCADE,
        related_name='pret_accorde',
        help_text="Demande de prêt associée"
    )
    
    client = models.ForeignKey(
        'accounts.Client',
        on_delete=models.CASCADE,
        related_name='prets',
        help_text="Client bénéficiaire du prêt"
    )
    
    montant_accorde = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Montant effectivement accordé"
    )
    
    statut = models.CharField(
        max_length=25,
        choices=StatutChoices.choices,
        default=StatutChoices.ACCORDE,
        help_text="Statut actuel du prêt"
    )
    
    date_creation = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de création du prêt (accord admin)"
    )
    
    date_decaissement = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date effective du décaissement"
    )
    
    admin_decaisseur = models.ForeignKey(
        'accounts.AdministrateurSFD',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prets_decaisses',
        help_text="Admin ayant marqué le prêt comme décaissé"
    )
    
    class Meta:
        verbose_name = "Prêt"
        verbose_name_plural = "Prêts"
        ordering = ['-date_creation']
        db_table = 'loans_loan'
        
        indexes = [
            models.Index(fields=['client', 'statut']),
            models.Index(fields=['date_creation']),
        ]
    
    def __str__(self):
        return f"Prêt #{self.id.hex[:8]} - {self.client.nom_complet} - {self.montant_accorde} FCFA"
    
    def marquer_decaisse(self, admin):
        """Marque le prêt comme décaissé physiquement"""
        if self.statut != self.StatutChoices.ACCORDE:
            raise ValidationError("Seuls les prêts accordés peuvent être décaissés")
        
        self.statut = self.StatutChoices.DECAISSE
        self.date_decaissement = timezone.now()
        self.admin_decaisseur = admin
        self.save()
        
        # Générer automatiquement le calendrier de remboursement
        self.generer_calendrier_remboursement()
        
        logger.info(f"Prêt {self.id} marqué comme décaissé par {admin}")
    
    def generer_calendrier_remboursement(self):
        """Génère automatiquement toutes les échéances de remboursement"""
        if not hasattr(self.demande, 'conditions_remboursement'):
            raise ValidationError("Les conditions de remboursement doivent être définies")
        
        conditions = self.demande.conditions_remboursement
        
        # Supprimer les échéances existantes si elles existent
        self.echeances.all().delete()
        
        # Générer toutes les échéances
        for i in range(self.demande.duree_pret):
            # Calcul de la date d'échéance (mois suivants)
            date_base = conditions.date_premiere_echeance
            if date_base.month + i <= 12:
                date_echeance = date_base.replace(month=date_base.month + i)
            else:
                # Gérer le passage d'année
                annees_ajoutees = (date_base.month + i - 1) // 12
                mois_final = (date_base.month + i - 1) % 12 + 1
                date_echeance = date_base.replace(
                    year=date_base.year + annees_ajoutees,
                    month=mois_final
                )
            
            RepaymentSchedule.objects.create(
                loan=self,
                numero_echeance=i + 1,
                date_echeance=date_echeance,
                montant_mensualite=conditions.montant_mensualite,
                montant_capital=0,  # À calculer
                montant_interet=0,  # À calculer
                solde_restant=0     # À calculer
            )
        
        # Calculer les répartitions capital/intérêt
        self._calculer_repartition_capital_interet()
        
        # Changer le statut
        self.statut = self.StatutChoices.EN_REMBOURSEMENT
        self.save()
        
        logger.info(f"Calendrier de remboursement généré pour le prêt {self.id}")
    
    def _calculer_repartition_capital_interet(self):
        """Calcule la répartition capital/intérêt pour chaque échéance"""
        conditions = self.demande.conditions_remboursement
        taux_mensuel = conditions.taux_interet_annuel / Decimal('12') / Decimal('100')
        solde_restant = self.montant_accorde
        
        for echeance in self.echeances.order_by('numero_echeance'):
            montant_interet = solde_restant * taux_mensuel
            montant_capital = conditions.montant_mensualite - montant_interet
            solde_restant -= montant_capital
            
            echeance.montant_interet = montant_interet
            echeance.montant_capital = montant_capital
            echeance.solde_restant = max(solde_restant, Decimal('0.00'))
            echeance.save()
    
    @property
    def montant_total_rembourse(self):
        """Calcule le montant total déjà remboursé"""
        return self.paiements.filter(statut='confirme').aggregate(
            total=models.Sum('montant_paye')
        )['total'] or Decimal('0.00')
    
    @property
    def solde_restant_du(self):
        """Calcule le solde restant dû"""
        total_du = self.demande.duree_pret * self.demande.conditions_remboursement.montant_mensualite
        return total_du - self.montant_total_rembourse
    
    @property
    def est_en_retard(self):
        """Vérifie si le prêt a des échéances en retard"""
        return self.echeances.filter(
            date_echeance__lt=timezone.now().date(),
            statut='en_attente'
        ).exists()


class RepaymentSchedule(models.Model):
    """
    Échéance de remboursement générée automatiquement.
    Une ligne par mensualité du prêt.
    """
    
    class StatutChoices(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        PAYE = 'paye', 'Payé'
        EN_RETARD = 'en_retard', 'En retard'
        PAYE_AVEC_PENALITES = 'paye_avec_penalites', 'Payé avec pénalités'
    
    loan = models.ForeignKey(
        'Loan',
        on_delete=models.CASCADE,
        related_name='echeances',
        help_text="Prêt associé"
    )
    
    numero_echeance = models.PositiveIntegerField(
        help_text="Numéro de l'échéance (1, 2, 3...)"
    )
    
    date_echeance = models.DateField(
        help_text="Date d'échéance de cette mensualité"
    )
    
    montant_mensualite = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Montant de la mensualité normale"
    )
    
    montant_capital = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Part capital de cette échéance"
    )
    
    montant_interet = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Part intérêt de cette échéance"
    )
    
    solde_restant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Solde restant après cette échéance"
    )
    
    statut = models.CharField(
        max_length=20,
        choices=StatutChoices.choices,
        default=StatutChoices.EN_ATTENTE,
        help_text="Statut de l'échéance"
    )
    
    date_paiement = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date effective du paiement"
    )
    
    montant_penalites = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Montant des pénalités de retard"
    )
    
    class Meta:
        verbose_name = "Échéance de Remboursement"
        verbose_name_plural = "Échéances de Remboursement"
        ordering = ['loan', 'numero_echeance']
        db_table = 'loans_repayment_schedule'
        unique_together = ['loan', 'numero_echeance']
        
        indexes = [
            models.Index(fields=['loan', 'date_echeance']),
            models.Index(fields=['date_echeance', 'statut']),
        ]
    
    def __str__(self):
        return f"Échéance {self.numero_echeance} - {self.loan.client.nom_complet} - {self.date_echeance}"
    
    def calculer_penalites(self):
        """Calcule les pénalités de retard pour cette échéance"""
        if self.statut == self.StatutChoices.PAYE:
            return Decimal('0.00')
        
        if timezone.now().date() <= self.date_echeance:
            return Decimal('0.00')
        
        # Calcul des jours de retard
        jours_retard = (timezone.now().date() - self.date_echeance).days
        
        # Calcul des pénalités selon le taux quotidien
        conditions = self.loan.demande.conditions_remboursement
        taux_quotidien = conditions.taux_penalite_quotidien / Decimal('100')
        penalites = self.montant_mensualite * taux_quotidien * jours_retard
        
        self.montant_penalites = penalites
        self.save(update_fields=['montant_penalites'])
        
        return penalites
    
    @property
    def montant_total_du(self):
        """Montant total dû (mensualité + pénalités)"""
        self.calculer_penalites()
        return self.montant_mensualite + self.montant_penalites
    
    @property
    def jours_retard(self):
        """Nombre de jours de retard"""
        if timezone.now().date() <= self.date_echeance:
            return 0
        return (timezone.now().date() - self.date_echeance).days


class Payment(models.Model):
    """
    Paiement effectué par le client via Mobile Money.
    Un paiement peut couvrir une ou plusieurs échéances.
    """
    
    class StatutChoices(models.TextChoices):
        EN_COURS = 'en_cours', 'En cours'
        CONFIRME = 'confirme', 'Confirmé'
        ECHEC = 'echec', 'Échec'
        REMBOURSE = 'rembourse', 'Remboursé'
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identifiant unique du paiement"
    )
    
    loan = models.ForeignKey(
        'Loan',
        on_delete=models.CASCADE,
        related_name='paiements',
        help_text="Prêt concerné par le paiement"
    )
    
    echeance = models.ForeignKey(
        'RepaymentSchedule',
        on_delete=models.CASCADE,
        related_name='paiements',
        help_text="Échéance remboursée"
    )
    
    montant_paye = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Montant effectivement payé"
    )
    
    montant_mensualite = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Montant de la mensualité normale"
    )
    
    montant_penalites = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Montant des pénalités incluses"
    )
    
    transaction_mobile_money = models.ForeignKey(
        'mobile_money.TransactionMobileMoney',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='remboursements_prets',
        help_text="Transaction Mobile Money associée"
    )
    
    statut = models.CharField(
        max_length=15,
        choices=StatutChoices.choices,
        default=StatutChoices.EN_COURS,
        help_text="Statut du paiement"
    )
    
    date_paiement = models.DateTimeField(
        auto_now_add=True,
        help_text="Date d'initiation du paiement"
    )
    
    date_confirmation = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de confirmation du paiement"
    )
    
    reference_externe = models.CharField(
        max_length=100,
        unique=True,
        help_text="Référence externe de la transaction"
    )
    
    class Meta:
        verbose_name = "Paiement de Remboursement"
        verbose_name_plural = "Paiements de Remboursement"
        ordering = ['-date_paiement']
        db_table = 'loans_payment'
        
        indexes = [
            models.Index(fields=['loan', 'statut']),
            models.Index(fields=['date_paiement']),
            models.Index(fields=['reference_externe']),
        ]
    
    def __str__(self):
        return f"Paiement {self.reference_externe} - {self.montant_paye} FCFA"
    
    def confirmer_paiement(self):
        """Confirme le paiement et met à jour l'échéance"""
        if self.statut != self.StatutChoices.EN_COURS:
            raise ValidationError("Seuls les paiements en cours peuvent être confirmés")
        
        self.statut = self.StatutChoices.CONFIRME
        self.date_confirmation = timezone.now()
        self.save()
        
        # Mettre à jour l'échéance
        echeance = self.echeance
        if self.montant_penalites > 0:
            echeance.statut = RepaymentSchedule.StatutChoices.PAYE_AVEC_PENALITES
        else:
            echeance.statut = RepaymentSchedule.StatutChoices.PAYE
        
        echeance.date_paiement = self.date_confirmation
        echeance.save()
        
        # Vérifier si le prêt est soldé
        loan = self.loan
        if not loan.echeances.filter(statut='en_attente').exists():
            loan.statut = Loan.StatutChoices.SOLDE
            loan.save()
            logger.info(f"Prêt {loan.id} complètement soldé")
        
        logger.info(f"Paiement {self.id} confirmé pour l'échéance {echeance.numero_echeance}")
    
    def save(self, *args, **kwargs):
        """Override save pour générer la référence externe"""
        if not self.reference_externe:
            self.reference_externe = f"PAY_{self.loan.id.hex[:8]}_{int(timezone.now().timestamp())}"
        super().save(*args, **kwargs)
