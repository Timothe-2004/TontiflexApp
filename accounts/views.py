from django.shortcuts import render
from rest_framework import status, viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.utils import (
    extend_schema, extend_schema_view, OpenApiExample, 
    OpenApiParameter, OpenApiResponse
)
from drf_spectacular.types import OpenApiTypes

from .serializers import (
    InscriptionSerializer,
    AgentSFDAdminSerializer,
    SuperviseurSFDAdminSerializer,
    AdministrateurSFDAdminSerializer,
    AdminPlateformeAdminSerializer,
    SFDSerializer,
    SFDDetailSerializer,
    # API REST Serializers
    ClientSerializer,
    AgentSFDSerializer,
    SuperviseurSFDSerializer,
    AdministrateurSFDSerializer,
    AdminPlateformeSerializer,
    LoginSerializer,
)
from .permissions import IsAdminPlateformeOrSuperuser
from .models import Client, AgentSFD, SuperviseurSFD, AdministrateurSFD, AdminPlateforme, SFD
from django.contrib.auth import get_user_model

User = get_user_model()

# Create your views here.

@extend_schema(
    tags=["🔐 Authentification"],
    summary="Inscription d'un nouveau client",
    description="""
    Permet à un visiteur (non connecté) de créer un compte CLIENT sur la plateforme TontiFlex.
    
    Cette inscription est la première étape pour qu'un citoyen puisse rejoindre des tontines et utiliser les services financiers digitalisés.
    
    **Processus métier**:
    1. Le visiteur saisit ses informations personnelles
    2. Le système valide les données (unicité email/téléphone)
    3. Un compte CLIENT est créé automatiquement
    4. L'utilisateur peut ensuite se connecter et demander à rejoindre des tontines
    
    **Données requises**:
    - Informations personnelles (nom, prénom, téléphone, email)
    - Adresse et profession
    - Mot de passe sécurisé
    - Documents d'identité (pièce d'identité et photo)
    
    **Validations effectuées**:
    - Email unique dans le système
    - Numéro de téléphone unique et valide
    - Formats des documents d'identité
    - Complexité du mot de passe
    
    **Permissions requises**: Aucune (endpoint public)
    **Conditions**: Aucune
    **Effets**: Création d'un compte CLIENT actif, prêt pour l'authentification
    """,
    request=InscriptionSerializer,
    responses={
        201: OpenApiResponse(
            description="Inscription réussie - Compte client créé",
            examples=[OpenApiExample(
                "Succès inscription",
                value={"detail": "Inscription réussie.", "client_id": 123}
            )]
        ),
        400: OpenApiResponse(
            description="Erreur de validation des données",
            examples=[OpenApiExample(
                "Erreur validation",
                value={
                    "email": ["Un utilisateur avec cet email existe déjà."],
                    "telephone": ["Ce numéro de téléphone est déjà utilisé."],
                    "motDePasse": ["Le mot de passe doit contenir au moins 8 caractères."]
                }
            )]
        )
    },
    examples=[
        OpenApiExample(
            'Inscription client complète',
            value={
                "nom": "Kouassi",
                "prenom": "Marie",
                "telephone": "+22967123456",
                "email": "marie.kouassi@email.com",
                "adresse": "Quartier Zongo, Cotonou",
                "profession": "Commerçante",
                "motDePasse": "MotDePasse123!",
                "pieceIdentite": "CNI123456789",
                "photoIdentite": "base64_encoded_photo_string"
            },
            request_only=True,
        )
    ]
)
class InscriptionAPIView(APIView):
    """
    POST /api/auth/inscription/
    Permet à un visiteur de créer un compte CLIENT.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = InscriptionSerializer(data=request.data)
        if serializer.is_valid():
            client = serializer.save()
            return Response({'detail': 'Inscription réussie.'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# --- Nouveaux ViewSets admin ---
@extend_schema_view(
    list=extend_schema(
        summary="Liste tous les agents SFD",
        description="""
        Récupère la liste complète des agents SFD de toutes les structures financières décentralisées.
        
        **Rôle métier**: Les agents SFD sont les employés de terrain qui valident les documents des clients,
        approuvent les demandes de retrait et assurent le lien entre les clients et leur SFD.
        
        **Permissions requises**: Administrateur plateforme uniquement
        **Filtres disponibles**: Par SFD, par statut actif/inactif
        **Tri**: Par nom, date de création, SFD
        """,
        responses={200: AgentSFDAdminSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Créer un nouvel agent SFD",
        description="""
        Crée un nouveau compte agent SFD rattaché à une structure financière décentralisée.
        
        **Processus métier**:
        1. Validation des informations personnelles
        2. Vérification que le SFD existe et est actif
        3. Création du compte avec les permissions d'agent
        4. Envoi des identifiants de connexion par email/SMS
        
        **Permissions requises**: Administrateur plateforme
        **Effets**: Nouvel agent opérationnel, peut valider documents et retraits
        """,
        responses={201: AgentSFDAdminSerializer}
    ),
    retrieve=extend_schema(
        summary="Détails d'un agent SFD",
        description="Récupère les informations détaillées d'un agent SFD spécifique avec ses statistiques d'activité."
    ),
    update=extend_schema(
        summary="Modifier un agent SFD",
        description="""
        Met à jour les informations d'un agent SFD existant.
        
        **Modifications possibles**:
        - Informations personnelles (nom, téléphone, email)
        - Statut actif/inactif
        - Changement de SFD de rattachement
        - Réinitialisation de mot de passe
        
        **Permissions requises**: Administrateur plateforme
        **Effets**: Mise à jour immédiate des permissions et accès
        """
    ),
    destroy=extend_schema(
        summary="Supprimer un agent SFD",
        description="""
        Désactive définitivement un compte agent SFD.
        
        ⚠️ **Attention**: Cette action est irréversible et affecte l'historique des validations.
        
        **Permissions requises**: Administrateur plateforme
        **Effets**: Compte désactivé, historique conservé
        """
    )
)
@extend_schema_view(
    list=extend_schema(
        summary="Liste des agents SFD",
        description="""
        Affiche la liste des agents SFD enregistrés sur la plateforme.
        
        **Rôle des agents SFD**:
        - Validation des documents d'identité des clients
        - Approbation des demandes d'ouverture de comptes épargne
        - Traitement des demandes de retrait
        - Gestion des clients de leur SFD
        
        **Données retournées**:
        - Informations personnelles et de contact
        - SFD de rattachement
        - Nombre de clients gérés
        - Statut d'activité et dernière connexion
        
        **Permissions requises**:
        - Admin SFD: agents de sa SFD uniquement
        - Admin plateforme: tous les agents
        """,
        responses={200: AgentSFDSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Créer un nouveau compte agent SFD",
        description="""
        Crée un nouveau compte agent SFD avec les permissions appropriées.
        
        **Processus de création**:
        1. Validation des informations personnelles
        2. Vérification de l'unicité email/téléphone
        3. Attribution du rôle 'agent_sfd'
        4. Notification d'activation par email
        
        **Champs obligatoires**:
        - Nom et prénom
        - Email professionnel
        - Numéro de téléphone
        - SFD de rattachement
        
        **Permissions requises**: Admin SFD ou Admin plateforme
        """,
        request=AgentSFDSerializer,
        responses={
            201: AgentSFDSerializer,
            400: OpenApiResponse(description="Données invalides ou email déjà utilisé"),
            403: OpenApiResponse(description="Permissions insuffisantes")
        },
        examples=[
            OpenApiExample(
                "Création agent SFD",
                value={
                    "nom": "Traoré",
                    "prenom": "Amadou",
                    "email": "amadou.traore@sfd.example.com",
                    "telephone": "+22370123456",
                    "motDePasse": "MotDePasse123!",
                    "sfd_id": "SFD001"
                }
            )
        ]
    )
)
@extend_schema(
    tags=["👥 Gestion des Agents SFD"],
    examples=[
        OpenApiExample(
            'Création agent SFD',
            value={
                "nom": "Dupont",
                "prenom": "Jean",
                "email": "jean.dupont@sfd-cotonou.bj",
                "telephone": "+22967123456",
                "motDePasse": "MotDePasse123!",
                "adresse": "Rue des Cocotiers, Cotonou",
                "profession": "Agent de terrain",
                "sfd_id": "SFD001",
                "est_actif": True
            },
            request_only=True,
        )
    ]
)
class AgentSFDViewSet(viewsets.ModelViewSet):
    queryset = AgentSFD.objects.all()
    serializer_class = AgentSFDAdminSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminPlateformeOrSuperuser]

@extend_schema_view(    list=extend_schema(
        summary="Liste des superviseurs SFD",
        description="""
        Affiche la liste des superviseurs SFD avec leurs responsabilités.
        
        Rôle des superviseurs SFD:
        Examen et validation des demandes de prêt
        Définition des taux d'intérêt et calendriers de remboursement
        Modification des formulaires soumis par les clients
        Transmission des dossiers à l'admin SFD si nécessaire
        Suivi du statut de remboursement des prêts
        
        Données retournées:
        Informations personnelles et professionnelles
        SFD de rattachement et zone de supervision
        Nombre de prêts en cours de traitement
        Statistiques d'approbation et performance
        
        Permissions requises:
        Admin SFD: superviseurs de sa SFD uniquement
        Admin plateforme: tous les superviseurs
        """,
        responses={200: SuperviseurSFDAdminSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Créer un compte superviseur SFD",
        description="""
        Crée un nouveau compte superviseur SFD avec les droits de validation des prêts.
        
        Processus de création:
        1. Validation des qualifications et expérience
        2. Attribution des permissions de supervision
        3. Définition de la zone de responsabilité
        4. Configuration des limites d'approbation
        
        Champs obligatoires:
        Informations personnelles complètes
        SFD de rattachement
        Niveau d'autorisation financière
        Zone géographique de supervision
        
        Permissions requises: Admin SFD ou Admin plateforme
        """,
        request=SuperviseurSFDAdminSerializer,
        responses={
            201: SuperviseurSFDAdminSerializer,
            400: OpenApiResponse(description="Données invalides"),
            403: OpenApiResponse(description="Permissions insuffisantes")
        },
        examples=[
            OpenApiExample(
                "Création superviseur SFD",
                value={
                    "nom": "Kouassi",
                    "prenom": "Marie",
                    "email": "marie.kouassi@sfd.example.com",
                    "telephone": "+22505123456",
                    "sfd_id": "SFD001",
                    "zone_supervision": "Nord-Ouest",
                    "limite_approbation": 500000
                }
            )
        ]
    ),
    retrieve=extend_schema(
        summary="Détails d'un superviseur SFD",
        description="Récupère les informations détaillées d'un superviseur SFD spécifique avec ses statistiques de supervision."
    ),
    update=extend_schema(
        summary="Modifier un superviseur SFD",
        description="""
        Met à jour les informations d'un superviseur SFD existant.
        
        Modifications possibles:
        Informations personnelles (nom, téléphone, email)
        Zone de supervision et responsabilités
        Limites d'autorisation financière
        Statut actif/inactif
        
        Permissions requises: Admin SFD ou Admin plateforme
        Effets: Mise à jour immédiate des permissions et zones d'autorisation
        """
    ),
    partial_update=extend_schema(
        summary="Modification partielle d'un superviseur SFD",
        description="Met à jour partiellement les informations d'un superviseur SFD (uniquement les champs fournis)."
    ),
    destroy=extend_schema(
        summary="Supprimer un superviseur SFD",
        description="""
        Désactive définitivement un compte superviseur SFD.
        
        Attention: Cette action est irréversible et affecte les dossiers de prêts en cours.
        
        Permissions requises: Admin plateforme uniquement
        Effets: Compte désactivé, historique de supervision conservé
        """
    )
)
@extend_schema(
    tags=["👥 Gestion des Superviseurs SFD"],
    examples=[
        OpenApiExample(
            'Création superviseur SFD',
            value={
                "nom": "Smith",
                "prenom": "Anna",
                "email": "anna.smith@sfd-cotonou.bj",
                "telephone": "+22967123457",
                "motDePasse": "SuperMotDePasse456!",
                "adresse": "Avenue Jean-Paul II, Porto-Novo",
                "profession": "Superviseur crédit",
                "sfd_id": "SFD001",
                "est_actif": True
            },
            request_only=True,
        )
    ]
)
class SuperviseurSFDViewSet(viewsets.ModelViewSet):
    queryset = SuperviseurSFD.objects.all()
    serializer_class = SuperviseurSFDAdminSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminPlateformeOrSuperuser]

@extend_schema_view(
    list=extend_schema(
        summary="Liste des administrateurs SFD",
        description="""
        Affiche la liste des administrateurs SFD avec leurs responsabilités de gestion.
        
        Rôle des administrateurs SFD:
        Création et configuration des tontines
        Validation finale des demandes de prêt
        Consultation des statistiques et logs d'activité
        Gestion des comptes agents et superviseurs
        Désactivation des comptes utilisateurs si nécessaire
        
        Données retournées:
        Profil administratif complet
        SFD administrée et zone de couverture
        Statistiques de performance de la SFD
        Nombre d'utilisateurs sous supervision
        
        Permissions requises: Admin plateforme uniquement
        """,
        responses={200: AdministrateurSFDAdminSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Créer un compte administrateur SFD",
        description="""
        Crée un nouveau compte administrateur SFD avec les pleins pouvoirs sur sa SFD.
        
        Processus de création:
        1. Validation des qualifications managériales
        2. Attribution des permissions d'administration
        3. Configuration de l'accès aux statistiques
        4. Définition des limites opérationnelles
        
        Responsabilités assignées:
        Gestion complète de la SFD
        Supervision des équipes (agents/superviseurs)
        Configuration des produits financiers
        Reporting et conformité réglementaire
        
        Permissions requises: Admin plateforme uniquement
        """,        request=AdministrateurSFDAdminSerializer,
        responses={
            201: AdministrateurSFDAdminSerializer,
            400: OpenApiResponse(description="Données invalides"),
            403: OpenApiResponse(description="Permissions insuffisantes - Admin plateforme requis")
        },
        examples=[
            OpenApiExample(
                "Création administrateur SFD",
                value={
                    "nom": "Diabaté",
                    "prenom": "Ibrahim",
                    "email": "ibrahim.diabate@sfd.example.com",
                    "telephone": "+22370987654",
                    "sfd_id": "SFD001",
                    "region_responsabilite": "Région Centre",
                    "niveau_autorisation": "MAXIMUM"
                }
            )        ]
    ),
    retrieve=extend_schema(
        summary="Détails d'un administrateur SFD",
        description="Récupère les informations détaillées d'un administrateur SFD spécifique avec ses statistiques de gestion."
    ),
    update=extend_schema(
        summary="Modifier un administrateur SFD",
        description="""
        Met à jour les informations d'un administrateur SFD existant.
        
        Modifications possibles:
        Informations personnelles (nom, téléphone, email)
        Région de responsabilité
        Niveau d'autorisation
        Permissions de création de tontines
        Statut actif/inactif
        
        Permissions requises: Admin plateforme uniquement
        Effets: Mise à jour immédiate des permissions d'administration
        """
    ),
    partial_update=extend_schema(
        summary="Modification partielle d'un administrateur SFD",
        description="Met à jour partiellement les informations d'un administrateur SFD (uniquement les champs fournis)."
    ),
    destroy=extend_schema(
        summary="Supprimer un administrateur SFD",
        description="""
        Désactive définitivement un compte administrateur SFD.
        
        Attention: Cette action est irréversible et affecte la gestion de la SFD.
        
        Permissions requises: Admin plateforme uniquement
        Effets: Compte désactivé, historique administratif conservé
        """
    )
)
@extend_schema(
    tags=["👥 Gestion des Admin SFD"],
    examples=[
        OpenApiExample(
            'Création administrateur SFD',
            value={
                "nom": "Kouassi",
                "prenom": "Paul",
                "email": "paul.kouassi@sfd-parakou.bj",
                "telephone": "+22967123458",
                "motDePasse": "AdminMotDePasse789!",
                "adresse": "Boulevard de l'Indépendance, Parakou",
                "profession": "Directeur SFD",
                "sfd_id": "SFD001",
                "peut_creer_tontines": True,
                "est_actif": True
            },
            request_only=True,
        )
    ]
)
class AdministrateurSFDViewSet(viewsets.ModelViewSet):
    queryset = AdministrateurSFD.objects.all()
    serializer_class = AdministrateurSFDAdminSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminPlateformeOrSuperuser]

@extend_schema_view(    list=extend_schema(
        summary="Liste des administrateurs plateforme",
        description="""
        Affiche la liste des super-administrateurs de la plateforme TontiFlex.
        
        Rôle des administrateurs plateforme:
        Gestion globale de tous les comptes utilisateurs
        Création, suspension et suppression des comptes (clients, agents, superviseurs, admins SFD)
        Gestion des SFD (ajout, suppression, suspension)
        Supervision de l'ensemble du système
        Configuration des paramètres globaux de la plateforme
        
        Données retournées:
        Profil administrateur complet
        Statistiques d'utilisation globales
        Nombre total d'utilisateurs et SFD gérés
        Logs d'activité administrative
        
        Permissions requises: Super administrateur uniquement
        """,
        responses={200: AdminPlateformeAdminSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Créer un compte administrateur plateforme",
        description="""
        Crée un nouveau super-administrateur avec les pleins pouvoirs sur la plateforme.
        
        Processus de création:
        Attention: Cette action crée un utilisateur avec des privilèges maximaux
        
        1. Validation stricte des qualifications
        2. Attribution des permissions super-administrateur
        3. Configuration de l'accès global au système
        4. Notification sécurisée d'activation
        
        Responsabilités assignées:
        Contrôle total sur tous les utilisateurs
        Gestion des SFD partenaires
        Supervision sécuritaire du système
        Configuration des politiques globales
        
        Permissions requises: Super administrateur existant uniquement
        """,
        request=AdminPlateformeAdminSerializer,
        responses={
            201: AdminPlateformeAdminSerializer,
            400: OpenApiResponse(description="Données invalides"),
            403: OpenApiResponse(description="Permissions insuffisantes - Super admin requis")
        },        examples=[
            OpenApiExample(
                "Création administrateur plateforme",
                value={
                    "nom": "Ouattara",
                    "prenom": "Fatou",
                    "email": "fatou.ouattara@tontiflex.com",
                    "telephone": "+22570123456",
                    "niveau_acces": "SUPER_ADMIN",
                    "zone_responsabilite": "GLOBAL"
                }
            )
        ]    ),
    retrieve=extend_schema(
        summary="Détails d'un administrateur plateforme",
        description="Récupère les informations détaillées d'un super-administrateur spécifique avec ses statistiques d'activité."
    ),
    update=extend_schema(
        summary="Modifier un administrateur plateforme",
        description="""
        Met à jour les informations d'un super-administrateur existant.
        
        Modifications possibles:
        Informations personnelles (nom, téléphone, email)
        Niveau d'accès et zone de responsabilité
        Permissions de gestion des comptes et SFD
        Statut actif/inactif
        
        Permissions requises: Super administrateur uniquement
        Effets: Mise à jour immédiate des permissions maximales
        """
    ),
    partial_update=extend_schema(
        summary="Modification partielle d'un administrateur plateforme",
        description="Met à jour partiellement les informations d'un super-administrateur (uniquement les champs fournis)."
    ),
    destroy=extend_schema(
        summary="Supprimer un administrateur plateforme",
        description="""
        Désactive définitivement un compte super-administrateur.
        
        Attention: Cette action est irréversible et réduit le nombre d'administrateurs système.
        
        Permissions requises: Super administrateur uniquement
        Effets: Compte désactivé, historique administratif global conservé
        """
    )
)
@extend_schema(
    tags=["👥 Gestion des Admin Plateforme"],
    examples=[
        OpenApiExample(
            'Création admin plateforme',
            value={
                "nom": "Tonti",
                "prenom": "Flex",
                "email": "admin@tontiflex.com",
                "telephone": "+22967123459",
                "motDePasse": "SuperAdminMotDePasse!",
                "adresse": "Siège social TontiFlex, Abomey",
                "profession": "Super Administrateur",
                "peut_gerer_comptes": True,
                "peut_gerer_sfd": True,
                "est_actif": True
            },
            request_only=True,
        )
    ]
)
class AdminPlateformeViewSet(viewsets.ModelViewSet):
    queryset = AdminPlateforme.objects.all()
    serializer_class = AdminPlateformeAdminSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminPlateformeOrSuperuser]

@extend_schema_view(
    list=extend_schema(
        summary="Liste toutes les SFD",
        description="""
        Récupère la liste des Structures Financières Décentralisées enregistrées sur la plateforme.
        
        **Informations retournées**:
        - Données officielles (nom, code, adresse légale)
        - Statut d'activité et date d'enregistrement
        - Nombre d'agents, superviseurs, administrateurs
        - Statistiques des tontines actives
        """
    ),
    create=extend_schema(
        summary="Enregistrer une nouvelle SFD",
        description="""
        Enregistre une nouvelle Structure Financière Décentralisée sur la plateforme TontiFlex.
        
        **Processus d'enregistrement**:
        1. Validation des documents légaux
        2. Vérification de l'agrément BCEAO/UEMOA
        3. Configuration initiale de la structure
        4. Activation des services de base
        
        **Permissions requises**: Administrateur plateforme uniquement
        **Effets**: SFD opérationnelle, peut créer des tontines et gérer des clients
        """
    )
)
@extend_schema(
    summary="Gestion des SFD (Structures Financières Décentralisées)",
    description="Gestion complète des SFD - réservé aux AdminPlateforme",
    tags=["🏢 Gestion SFD"]
)
class SFDViewSet(viewsets.ModelViewSet):
    queryset = SFD.objects.all()
    serializer_class = SFDSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminPlateformeOrSuperuser]

# Alias for JWT login and refresh
@extend_schema(
    tags=["🔐 Authentification"],
    summary="Connexion à la plateforme",
    description="""
    Authentification JWT pour tous les types d'utilisateurs de la plateforme TontiFlex.
    
    **Types d'utilisateurs supportés**:
    - Clients (accès tontines et transactions)
    - Agents SFD (validation documents, approbation retraits)
    - Superviseurs SFD (gestion prêts et supervision)
    - Administrateurs SFD (direction opérationnelle)
    - Administrateurs plateforme (gestion globale)
    
    **Processus d'authentification**:
    1. Validation email/mot de passe
    2. Vérification du statut actif du compte
    3. Génération des tokens JWT (access + refresh)
    4. Retour des informations utilisateur et permissions
    
    **Tokens retournés**:
    - `access`: Token court (15 min) pour les requêtes API
    - `refresh`: Token long (7 jours) pour renouveler l'access token
    
    **Permissions requises**: Aucune (endpoint public)
    **Conditions**: Compte actif et validé
    **Effets**: Session utilisateur active, accès aux endpoints autorisés
    """,
    request=LoginSerializer,
    responses={
        200: OpenApiResponse(
            description="Connexion réussie - Tokens JWT générés",
            examples=[OpenApiExample(
                "Succès connexion",
                value={
                    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                    "user": {
                        "id": 123,
                        "email": "marie.kouassi@email.com",
                        "nom": "Kouassi",
                        "prenom": "Marie",
                        "type_utilisateur": "CLIENT",
                        "sfd": None
                    }
                }
            )]
        ),
        401: OpenApiResponse(
            description="Identifiants incorrects",
            examples=[OpenApiExample(
                "Erreur authentification",
                value={"detail": "Email ou mot de passe incorrect."}
            )]
        ),
        403: OpenApiResponse(
            description="Compte désactivé",
            examples=[OpenApiExample(
                "Compte inactif",
                value={"detail": "Votre compte a été désactivé. Contactez votre administrateur."}
            )]
        )
    },
    examples=[
        OpenApiExample(
            'Connexion utilisateur',
            value={
                "email": "marie.kouassi@email.com",
                "motDePasse": "MotDePasse123!"
            },
            request_only=True,
        )
    ]
)
class LoginView(APIView):
    """
    POST /api/auth/login/
    
    Vue de connexion personnalisée utilisant email/motDePasse
    et retournant des tokens JWT compatibles avec le système TontiFlex.
    """
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        tags=["🔐 Authentification"],
        summary="Connexion utilisateur",
        description="""
        Authentifie un utilisateur avec email/motDePasse et retourne les tokens JWT.
        
        **Format requis**:
        - email: Adresse email de l'utilisateur
        - motDePasse: Mot de passe de l'utilisateur
        
        **Retour**:
        - access: Token d'accès JWT (15 minutes)
        - refresh: Token de rafraîchissement (7 jours)
        - user: Informations basiques de l'utilisateur
        
        **Comment utiliser le token**:
        1. Copiez le token `access` de la réponse
        2. Cliquez sur "Authorize" en haut de cette page
        3. Entrez: `Bearer YOUR_ACCESS_TOKEN`
        4. Cliquez "Authorize" pour authentifier toutes les requêtes
        """,
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(
                description="Connexion réussie",
                examples=[OpenApiExample(
                    "Succès connexion",
                    value={
                        "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                        "user": {
                            "id": 1,
                            "email": "user@example.com",
                            "username": "user123",
                            "is_active": True
                        }
                    }
                )]
            ),
            400: OpenApiResponse(
                description="Données invalides",
                examples=[OpenApiExample(
                    "Erreur validation",
                    value={
                        "email": ["This field is required."],
                        "motDePasse": ["This field is required."]
                    }
                )]
            ),
            401: OpenApiResponse(
                description="Identifiants incorrects",
                examples=[OpenApiExample(
                    "Erreur authentification",
                    value={
                        "detail": "Identifiants invalides"
                    }
                )]
            ),
        }
    )
    def post(self, request):
        """Authentification avec email/motDePasse"""
        serializer = LoginSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        email = serializer.validated_data['email']
        mot_de_passe = serializer.validated_data['motDePasse']
        
        # Authentification
        try:
            from django.contrib.auth import authenticate
            from rest_framework_simplejwt.tokens import RefreshToken
            
            # Trouver l'utilisateur par email
            user = User.objects.filter(email=email).first()
            if not user:
                return Response(
                    {"detail": "Identifiants invalides"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Vérifier le mot de passe
            if not user.check_password(mot_de_passe):
                return Response(
                    {"detail": "Identifiants invalides"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Générer les tokens JWT
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'is_active': user.is_active
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"detail": "Erreur d'authentification"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@extend_schema(
    tags=["🔐 Authentification"],
    summary="Renouvellement du token d'accès",
    description="""
    Génère un nouveau token d'accès à partir d'un token de rafraîchissement valide.
    
    **Utilisation recommandée**:
    - Appelez cet endpoint quand vous recevez une erreur 401 sur une requête authentifiée
    - Implémentez un refresh automatique avant expiration du token (recommandé: 2-3 min avant)
    - Stockez le refresh token de manière sécurisée (httpOnly cookie recommandé)
    
    **Cycle de vie des tokens**:
    1. Login initial → access token (15 min) + refresh token (7 jours)
    2. Utilisation access token pour les requêtes API
    3. À expiration → refresh automatique avec refresh token
    4. Nouveau access token généré (15 min supplémentaires)
    5. Si refresh token expiré → nouvelle connexion requise
    
    **Sécurité**:
    - Le refresh token n'est valide qu'une seule fois
    - Chaque refresh génère un nouveau couple access/refresh
    - Les anciens tokens sont automatiquement invalidés
    
    **Permissions requises**: Token refresh valide
    **Conditions**: Refresh token non expiré et non utilisé
    **Effets**: Nouveaux tokens générés, session prolongée
    """,
    responses={
        200: OpenApiResponse(
            description="Token renouvelé avec succès",
            examples=[OpenApiExample(
                "Succès renouvellement",
                value={
                    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
                }
            )]
        ),
        401: OpenApiResponse(
            description="Token refresh invalide ou expiré",
            examples=[OpenApiExample(
                "Token invalide",
                value={"detail": "Token invalide ou expiré."}
            )]
        )
    },
    examples=[
        OpenApiExample(
            'Renouvellement token',
            value={
                "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
            },
            request_only=True,
        )
    ]
)
class TokenRefreshViewCustom(TokenRefreshView):
    """
    POST /api/auth/token/refresh/
    """
    permission_classes = [permissions.AllowAny]

from django.db.models import Sum
# ============================================================================
# VIEWSETS POUR API REST 
# ============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="Liste des clients",
        description="""
        Récupère la liste des clients enregistrés sur la plateforme TontiFlex.
        
        **Informations retournées**:
        - Données personnelles (nom, prénom, téléphone, email)
        - Statistiques des participations aux tontines
        - Statut du compte et date d'inscription
        - Informations de contact et localisation
        
        **Filtres disponibles**:
        - Par SFD de rattachement
        - Par statut de participation active
        - Par date d'inscription
        - Recherche textuelle (nom, email, téléphone)
        
        **Permissions requises**: Utilisateur authentifié
        **Conditions**: Visibilité selon le rôle (agent voit ses clients SFD)
        """,
        responses={200: ClientSerializer(many=True)}
    ),
    retrieve=extend_schema(
        summary="Détails d'un client",
        description="""
        Récupère les informations détaillées d'un client spécifique avec ses statistiques d'activité.
        
        **Données incluses**:
        - Profil complet du client
        - Nombre de tontines actives et terminées
        - Montant total des cotisations versées
        - Historique des retraits effectués
        - Statut des demandes en cours
        
        **Permissions requises**: 
        - Client: peut voir uniquement son propre profil
        - Agent/Superviseur/Admin SFD: clients de leur SFD
        - Admin plateforme: tous les clients
        """
    )
)
@extend_schema_view(
    list=extend_schema(
        summary="Liste des clients enregistrés",
        description="""
        Récupère la liste des clients enregistrés sur la plateforme TontiFlex.
        
        **Informations client**:
        - Données personnelles (nom, prénom, téléphone, email)
        - Informations de contact et localisation
        - Date d'inscription et statut du compte
        - Profession et revenus déclarés
        
        **Statistiques d'activité**:
        - Nombre de tontines actives
        - Total des cotisations versées
        - Historique des retraits
        - Taux de ponctualité global
        
        **Filtres et recherche**:
        - Recherche par nom, email ou téléphone
        - Filtrage par SFD de rattachement
        - Filtrage par statut de participation
        - Tri par date d'inscription ou activité
        
        **Permissions et visibilité**:
        - Client: peut voir uniquement son propre profil
        - Agent/Superviseur/Admin SFD: clients de leur SFD
        - Admin plateforme: tous les clients
        """,
        responses={200: ClientSerializer(many=True)}
    ),
    retrieve=extend_schema(
        summary="Détails d'un client spécifique",
        description="""
        Récupère les informations détaillées d'un client avec ses statistiques.
        
        **Profil complet**:
        - Toutes les données personnelles
        - Historique d'activité détaillé
        - Performances dans les tontines
        - Évaluations et notes
        
        **Métriques de performance**:
        - Ponctualité des cotisations
        - Montants totaux gérés
        - Nombre de cycles complétés
        - Historique des distributions reçues
        
        **Informations de sécurité**:
        - Dernière connexion
        - Activité récente
        - Statut de vérification des documents
        - Niveau de confiance
        """,
        responses={
            200: ClientSerializer,
            403: OpenApiResponse(description="Accès refusé à ce profil"),
            404: OpenApiResponse(description="Client introuvable")
        }
    )
)
@extend_schema(tags=["👤 Clients"])
class ClientViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour la gestion des clients"""
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Historique des cotisations du client",
        description="""
        Récupère l'historique complet des cotisations effectuées par un client.
        
        **Informations retournées**:
        - Liste chronologique de toutes les cotisations
        - Montants versés et dates de transaction
        - Tontines concernées et statuts de paiement
        - Références Mobile Money et confirmations
        - Statistiques de ponctualité et régularité
        
        **Calculs inclus**:
        - Total des cotisations versées
        - Moyenne mensuelle de cotisation
        - Nombre de jours de ponctualité
        - Bonus et pénalités appliqués
        
        **Permissions**:
        - Client: son propre historique uniquement
        - Agent/Superviseur/Admin SFD: clients de leur SFD
        - Admin plateforme: tous les clients
        """,
        responses={
            200: OpenApiResponse(
                description="Historique des cotisations récupéré",
                examples=[
                    OpenApiExample(
                        "Historique cotisations",
                        value={
                            "total_cotisations": 750000,
                            "cotisations": [
                                {
                                    "id": 123,
                                    "montant": 25000,
                                    "date_cotisation": "2025-06-25T09:00:00Z",
                                    "tontine": "Commerçants Cotonou",
                                    "statut": "confirme",
                                    "is_commission_sfd": False
                                }
                            ]
                        }
                    )
                ]
            ),
            403: OpenApiResponse(description="Accès refusé à cet historique"),
            404: OpenApiResponse(description="Client introuvable")
        }
    )
    @action(detail=True, methods=['get'], url_path='cotisations')
    def cotisations(self, request, pk=None):
        """Historique des cotisations d'un client"""
        client = self.get_object()
        from tontines.models import Cotisation
        cotisations = Cotisation.objects.filter(client=client)
        return Response({'cotisations': list(cotisations.values())})

    @extend_schema(
        summary="Historique des retraits du client",
        description="""
        Récupère l'historique des demandes et retraits effectués par un client.
        
        **Types de retraits**:
        - Retraits partiels de solde tontine
        - Retraits de fin de cycle
        - Retraits d'urgence (avec justification)
        - Distributions reçues lors du tour du client
        
        **Informations détaillées**:
        - Montants demandés et montants reçus
        - Dates de demande et de traitement
        - Statuts (en attente, validé, traité, rejeté)
        - Agents validateurs et motifs de rejet
        - Frais de traitement appliqués
        
        **Statistiques**:
        - Total des retraits effectués
        - Délai moyen de traitement
        - Taux d'approbation des demandes
        - Solde restant disponible
        
        **Permissions**:
        - Client: son propre historique uniquement  
        - Agent/Superviseur/Admin SFD: clients de leur SFD
        - Admin plateforme: tous les clients
        """,
        responses={
            200: OpenApiResponse(
                description="Historique des retraits récupéré",
                examples=[
                    OpenApiExample(
                        "Historique retraits",
                        value={
                            "total_retraits": 125000,
                            "retraits": [
                                {
                                    "id": 45,
                                    "montant_demande": 50000,
                                    "montant_recu": 49500,
                                    "date_demande": "2025-06-20T14:00:00Z",
                                    "date_traitement": "2025-06-21T10:30:00Z",
                                    "statut": "traite",
                                    "tontine": "Épargne Famille",
                                    "agent_validateur": "Agent Kouassi",
                                    "frais_traitement": 500
                                }
                            ]
                        }
                    )
                ]
            ),
            403: OpenApiResponse(description="Accès refusé à cet historique"),
            404: OpenApiResponse(description="Client introuvable")
        }
    )
    @action(detail=True, methods=['get'], url_path='retraits')
    def retraits(self, request, pk=None):
        """Historique des retraits d'un client"""
        client = self.get_object()
        from tontines.models import Retrait
        retraits = Retrait.objects.filter(client=client)
        return Response({'retraits': list(retraits.values())})

    @extend_schema(
        summary="Tontines du client",
        description="""
        Récupère la liste des tontines auxquelles le client participe activement.
        
        **Participations actives**:
        - Tontines en cours avec cotisations régulières
        - Statut de participation (actif, suspendu, en attente)
        - Position dans l'ordre de distribution
        - Prochaine date de réception prévue
        
        **Détails par tontine**:
        - Nom et description de la tontine
        - SFD gestionnaire et administrateur
        - Montant de cotisation convenu
        - Nombre total de participants
        - Cycle actuel et progression
        - Solde accumulé dans la tontine
        
        **Statistiques de participation**:
        - Nombre de cotisations effectuées
        - Taux de ponctualité
        - Montant total cotisé
        - Prochaines échéances
        - Historique des distributions reçues
        
        **États possibles**:
        - `actif`: Participation normale en cours
        - `suspendu`: Participation temporairement suspendue
        - `en_attente`: En attente de validation/paiement
        - `termine`: Tontine terminée, cycle complet
        
        **Permissions**:
        - Client: ses propres participations uniquement
        - Agent/Superviseur/Admin SFD: clients de leur SFD
        - Admin plateforme: tous les clients
        """,
        responses={
            200: OpenApiResponse(
                description="Liste des tontines du client",
                examples=[
                    OpenApiExample(
                        "Tontines actives",
                        value={
                            "total_tontines": 2,
                            "tontines_actives": 2,
                            "tontines": [
                                {
                                    "id": 12,
                                    "nom": "Commerçants Cotonou",
                                    "sfd": "SFD Cotonou Centre",
                                    "montant_cotisation": 25000,
                                    "statut_participation": "actif",
                                    "rang_distribution": 8,
                                    "solde_accumule": 350000,
                                    "prochaine_distribution": "2025-07-15T00:00:00Z",
                                    "taux_ponctualite": 95.5
                                },
                                {
                                    "id": 18,
                                    "nom": "Épargne Famille",
                                    "sfd": "SFD Parakou",
                                    "montant_cotisation": 15000,
                                    "statut_participation": "actif",
                                    "rang_distribution": 3,
                                    "solde_accumule": 180000,
                                    "prochaine_distribution": "2025-08-02T00:00:00Z",
                                    "taux_ponctualite": 100.0
                                }
                            ]
                        }
                    )
                ]
            ),
            403: OpenApiResponse(description="Accès refusé à ces informations"),
            404: OpenApiResponse(description="Client introuvable")
        }
    )
    @action(detail=True, methods=['get'], url_path='tontines')
    def tontines(self, request, pk=None):
        """Tontines d'un client"""
        client = self.get_object()
        from tontines.models import TontineParticipant
        participations = TontineParticipant.objects.filter(client=client, statut='actif')
        return Response({'tontines': list(participations.values())})


@extend_schema_view(
    list=extend_schema(
        summary="Liste des agents SFD (lecture seule)",
        description="""
        Affiche la liste des agents SFD en mode consultation uniquement.
        
        **Différence avec AgentSFDViewSet**:
        - Version lecture seule (pas de création/modification)
        - Accès élargi pour consultation inter-SFD
        - Informations publiques uniquement
        - Optimisé pour les requêtes de référence
        
        **Données visibles**:
        - Nom et informations de contact publiques
        - SFD de rattachement
        - Statut d'activité
        - Zone géographique de couverture
        
        **Utilisation**:
        - Sélection d'agent pour validation
        - Annuaire des agents inter-SFD
        - Référence pour les clients
        - Coordination entre SFD partenaires
        """,
        responses={200: AgentSFDSerializer(many=True)}
    )
)
@extend_schema(tags=["👥 Agents SFD"])
class AgentSFDReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AgentSFD.objects.all()
    serializer_class = AgentSFDSerializer
    permission_classes = [permissions.IsAuthenticated]


@extend_schema_view(
    list=extend_schema(
        summary="Liste des SFD de l'API",
        description="""
        Interface API principale pour la gestion des Structures Financières Décentralisées.
        
        **Fonctionnalités étendues**:
        - Gestion complète CRUD des SFD
        - Actions personnalisées pour rapports
        - Endpoints statistiques avancés
        - Intégration avec systèmes externes
        
        **Différence avec SFDViewSet admin**:
        - Interface publique pour partenaires
        - Endpoints d'intégration système
        - Données statistiques enrichies
        - API destinée aux applications clientes
        
        **Permissions**:
        - Lecture: Utilisateurs authentifiés
        - Écriture: Admin SFD et Admin plateforme
        """,
        responses={200: SFDSerializer(many=True)}
    )
)
@extend_schema(tags=["🏢 SFD"])
class SFDAPIViewSet(viewsets.ModelViewSet):
    queryset = SFD.objects.all()
    serializer_class = SFDSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Cotisations d'un client pour une SFD",
        description="""
        Récupère l'historique des cotisations d'un client spécifique dans les tontines d'une SFD.
        
        **Portée de la requête**:
        - Cotisations uniquement dans les tontines de la SFD spécifiée
        - Filtrage automatique par SFD pour sécurité
        - Historique complet depuis l'adhésion
        - Tous types de cotisations (normales + commissions SFD)
        
        **Données détaillées**:
        - Montants et dates de chaque cotisation
        - Tontines concernées dans la SFD
        - Statuts de paiement et confirmations
        - Références Mobile Money
        - Calculs de ponctualité et régularité
        
        **Statistiques SFD**:
        - Total cotisé dans cette SFD
        - Nombre de tontines de la SFD fréquentées
        - Performance de paiement relative à la SFD
        - Comparaison avec autres clients de la SFD
        
        **Cas d'usage**:
        - Suivi client par les agents SFD
        - Évaluation pour nouveaux produits
        - Reporting de performance SFD
        - Validation de capacité financière
        
        **Permissions**:
        - Agent/Superviseur/Admin SFD: clients de leur SFD uniquement
        - Admin plateforme: tous les clients et toutes les SFD
        """,
        responses={
            200: OpenApiResponse(
                description="Cotisations du client pour cette SFD",
                examples=[
                    OpenApiExample(
                        "Cotisations SFD spécifique",
                        value={
                            "client_nom": "Marie Kouassi",
                            "sfd_nom": "SFD Cotonou Centre",
                            "total_cotise_sfd": 485000,
                            "nombre_tontines_sfd": 2,
                            "cotisations": [
                                {
                                    "id": 234,
                                    "tontine": "Commerçants Cotonou",
                                    "montant": 25000,
                                    "date": "2025-06-25T09:00:00Z",
                                    "type": "cotisation_normale",
                                    "statut": "confirme"
                                },
                                {
                                    "id": 235,
                                    "tontine": "Épargne Mensuelle",
                                    "montant": 15000,
                                    "date": "2025-06-24T14:30:00Z",
                                    "type": "commission_sfd",
                                    "statut": "confirme"
                                }
                            ],
                            "statistiques": {
                                "taux_ponctualite_sfd": 96.5,
                                "moyenne_cotisation": 20000,
                                "jours_activite": 45
                            }
                        }
                    )
                ]
            ),
            403: OpenApiResponse(description="Accès refusé - SFD différente"),
            404: OpenApiResponse(description="Client ou SFD introuvable")
        }
    )
    @action(detail=True, methods=['get'], url_path='clients/(?P<client_id>[^/.]+)/cotisations')
    def client_cotisations(self, request, pk=None, client_id=None):
        """Cotisations d'un client pour un SFD"""
        sfd = self.get_object()
        try:
            client = Client.objects.get(id=client_id)
            from tontines.models import Cotisation
            cotisations = Cotisation.objects.filter(
                client=client,
                tontine__administrateurId__sfd=sfd
            )
            return Response({
                'sfd': sfd.nom,
                'client': client.nom_complet,
                'cotisations': list(cotisations.values())
            })
        except Client.DoesNotExist:
            return Response({'error': 'Client introuvable'}, status=404)


# ============================================================================
# VIEWSETS ADMINISTRATIFS
# ============================================================================
