from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.core.validators import EmailValidator, RegexValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
import uuid
from django.contrib.auth import get_user_model

from django.core.validators import FileExtensionValidator
from decimal import Decimal


User = get_user_model()

class Utilisateur(models.Model):
    """
    Classe parent abstraite pour tous les utilisateurs de TontiFlex.
    Définit les attributs et méthodes communs à tous les types d'utilisateurs.
    """
    
    # Choix pour le statut
    class StatutChoices(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        INACTIF = 'inactif', 'Inactif'
        SUSPENDU = 'suspendu', 'Suspendu'
    
    # Attributs
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        help_text="Identifiant unique de l'utilisateur"
    )
    
    nom = models.CharField(
        max_length=100,
        help_text="Nom de famille de l'utilisateur"
    )
    
    prenom = models.CharField(
        max_length=100,
        help_text="Prénom de l'utilisateur"
    )
    
    telephone = models.CharField(
        max_length=15,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Le numéro de téléphone doit être au format international."
            )
        ],
        help_text="Numéro de téléphone unique"
    )
    
    email = models.EmailField(
        unique=True,
        validators=[EmailValidator()],
        help_text="Adresse email unique"
    )
    
    adresse = models.TextField(
        help_text="Adresse physique complète"
    )
    
    profession = models.CharField(
        max_length=100,
        help_text="Profession de l'utilisateur"
    )
    
    motDePasse = models.CharField(
        max_length=128,
        help_text="Mot de passe hashé"
    )
    
    dateCreation = models.DateTimeField(
        default=timezone.now,
        help_text="Date de création du compte"
    )
    statut = models.CharField(
        max_length=20,
        choices=StatutChoices.choices,
        default=StatutChoices.ACTIF,
        help_text="Statut du compte utilisateur"
    )
    
    # Champs pour la gestion de session
    derniere_connexion = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Date de la dernière connexion"
    )
    
    
    email_verifie = models.BooleanField(
        default=False,
        help_text="Indique si l'email a été vérifié"
    )    
    class Meta:
        abstract = True
        ordering = ['-dateCreation']
    
    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.email})"
    
    def save(self, *args, **kwargs):
        """
        Override save pour hasher le mot de passe et synchroniser les dates de connexion.
        Compatible avec le système de synchronisation automatique avec Django User.
        """
        # Hasher le mot de passe uniquement s'il n'est pas déjà hashé
        if self.motDePasse and not self.motDePasse.startswith('pbkdf2_'):
            self.motDePasse = make_password(self.motDePasse)
            
        
        
        # Sauvegarder le modèle
        super().save(*args, **kwargs)
        
        # Note: La synchronisation avec Django User est gérée par les signaux
        # dans core.signals.py pour éviter les conflits
    
    
    @property
    def nom_complet(self):
        """Retourne le nom complet de l'utilisateur"""
        return f"{self.prenom} {self.nom}"
    
    @property
    def est_actif(self):
        """Vérifie si l'utilisateur est actif"""
        return self.statut == self.StatutChoices.ACTIF
    





class Client(Utilisateur):
    """
    Modèle Client héritant de Utilisateur.
    Représente un client du SFD pouvant adhérer aux tontines, 
    créer des comptes épargne et demander des prêts.
    """
    
    # Relation avec le modèle User de Django pour l'authentification
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='clientsfd',
        null=True,
        blank=True,
        help_text="Utilisateur Django associé pour l'authentification"
    )
    
    # Attributs spécifiques au Client
    pieceIdentite = models.FileField(
        upload_to='documents/pieces_identite/',
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'jpg', 'jpeg', 'png']
            )
        ],
        null=True,
        blank=True,
        help_text="Copie numérique de la pièce d'identité"
    )
    
    photoIdentite = models.ImageField(
        upload_to='documents/photos_identite/',
        validators=[
            FileExtensionValidator(
                allowed_extensions=['jpg', 'jpeg', 'png']
            )
        ],
        null=True,
        blank=True,
        help_text="Photo d'identité du client"
    )
    
    scorefiabilite = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Score de fiabilité basé sur l'historique des transactions"
    )
    
    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        db_table = 'core_client'
    
    def __str__(self):
        return f"Client: {self.nom_complet} - Score: {self.scorefiabilite}"
    
    
    @property
    def tontines(self):
        """Retourne les tontines auxquelles le client participe"""
        try:
            # Import local pour éviter les imports circulaires
            from tontines.models.tontine import Tontine
            return Tontine.objects.filter(participants=self)
        except Exception:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    @property
    def compteEpargne(self):
        """Retourne le compte épargne du client"""
        try:
            # Import local pour éviter les imports circulaires
            from epargne.models.compte import CompteEpargne
            return CompteEpargne.objects.get(clientId=self)
        except:
            return None
    
    @property
    def prets(self):
        """Retourne les prêts du client"""
        try:
            # Import local pour éviter les imports circulaires
            from pret.models.pret import Pret
            return Pret.objects.filter(clientId=self)
        except Exception:
            from django.db.models import QuerySet
            return QuerySet().none()
    
    @property
    def transactions(self):
        """Retourne toutes les transactions du client"""
        try:
            # Import local pour éviter les imports circulaires
            from epargne.models.transaction import Transaction
            return Transaction.objects.filter(clientId=self)
        except Exception:
            from django.db.models import QuerySet
            return QuerySet().none()




from django.db import models
from django.utils import timezone

class SFD(models.Model):
    """
    Modèle représentant une Structure de Finance Décentralisée (SFD).
    """
    id = models.CharField(primary_key=True, max_length=50, unique=True)
    nom = models.CharField(max_length=255)
    adresse = models.CharField(max_length=255)

    telephone = models.CharField(max_length=30)
    email = models.EmailField(max_length=255)
    numeroMobileMoney = models.CharField(max_length=30, help_text="Numéro Mobile Money principal de la SFD")
    dateCreation = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.nom} ({self.id})"




class AgentSFD(Utilisateur):
    """
    Modèle représentant un agent d'une Structure de Finance Décentralisée (SFD).
    L'agent est responsable de la validation des demandes d'adhésion et de retrait.
    """
    
    # Lien avec le User Django
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='agentsfd', null=True, blank=True, help_text="Compte Django lié à cet agent")
    # Référence à la SFD à laquelle appartient l'agent
    sfd = models.ForeignKey(SFD, on_delete=models.CASCADE, related_name="agents_sfd", help_text="SFD de rattachement",null=True)
    
    # Indicateur d'activité de l'agent
    est_actif = models.BooleanField(
        default=True,
        help_text="Indique si l'agent est actuellement actif"
    )
    
    
    
    class Meta:
        verbose_name = "Agent SFD"
        verbose_name_plural = "Agents SFD"
        db_table = "agent_sfd"
    
    def __str__(self):
        return f"Agent {self.nom} {self.prenom} - SFD: {self.sfd.nom if self.sfd else ''}"
    




class SuperviseurSFD(Utilisateur):
    """
    Modèle représentant un superviseur d'une Structure de Finance Décentralisée (SFD).
    Le superviseur examine les demandes de prêt et supervise les agents.
    """
    
    # Lien avec le User Django
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='superviseurssfd', null=True, blank=True, help_text="Compte Django lié à ce superviseur")
    # Référence à la SFD à laquelle appartient le superviseur
    sfd = models.ForeignKey(SFD, on_delete=models.CASCADE, related_name="superviseurs_sfd", help_text="SFD supervisée", null=True)
    

    
    # Indicateur d'activité
    est_actif = models.BooleanField(
        default=True,
        help_text="Indique si le superviseur est actuellement actif"
    )
    
   
    class Meta:
        verbose_name = "Superviseur SFD"
        verbose_name_plural = "Superviseurs SFD"
        db_table = "superviseur_sfd"
    
    def __str__(self):
        return f"Superviseur {self.nom} {self.prenom} - SFD: {self.sfd.nom if self.sfd else ''}"
    



from django.db import models
from django.core.validators import MinLengthValidator
from django.utils import timezone
from django.db.models import Count, Sum, Q



class AdministrateurSFD(Utilisateur):
    """
    Modèle représentant un administrateur d'une Structure de Finance Décentralisée (SFD).
    L'administrateur gère les tontines et valide les prêts importants.
    """
    
    # Lien avec le User Django
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='administrateurssfd', null=True, blank=True, help_text="Compte Django lié à cet administrateur SFD")
    # Référence à la SFD administrée
    sfd = models.ForeignKey(SFD, on_delete=models.CASCADE, related_name="administrateurs_sfd", help_text="SFD administrée",null=True)
      
    
    # Permissions spéciales
    peut_creer_tontines = models.BooleanField(
        default=True,
        help_text="Autorisation pour créer des tontines"
    )
    
   
  
    
  
    # Indicateur d'activité
    est_actif = models.BooleanField(
        default=True,
        help_text="Indique si l'administrateur est actuellement actif"
    )
    
    class Meta:
        verbose_name = "Administrateur SFD"
        verbose_name_plural = "Administrateurs SFD"
        db_table = "administrateur_sfd"
    
    def __str__(self):
        return f"Admin {self.nom} {self.prenom} - SFD: {self.sfd.nom if self.sfd else ''}"
    



class AdminPlateforme(Utilisateur):
    """
    Modèle représentant l'administrateur de la plateforme TontiFlex.
    Il gère tous les comptes (clients, agents, admins SFD, superviseurs) et les SFD.
    """
    # Lien avec le User Django
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='adminplateforme', null=True, blank=True, help_text="Compte Django lié à cet admin plateforme")

    # Permissions globales
    peut_gerer_comptes = models.BooleanField(
        default=True,
        help_text="Peut créer, suspendre, supprimer les comptes clients, agents, admins SFD, superviseurs"
    )
    peut_gerer_sfd = models.BooleanField(
        default=True,
        help_text="Peut ajouter, supprimer, suspendre des SFD"
    )
    est_actif = models.BooleanField(
        default=True,
        help_text="Indique si l'admin plateforme est actuellement actif"
    )

    class Meta:
        verbose_name = "Admin Plateforme"
        verbose_name_plural = "Admins Plateforme"
        db_table = "admin_plateforme"

    def __str__(self):
        return f"AdminPlateforme {self.nom} {self.prenom} ({self.email})"

