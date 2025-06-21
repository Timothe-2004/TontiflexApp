from django.shortcuts import render
from rest_framework import status, viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.utils import extend_schema, OpenApiExample

from .serializers import (
    InscriptionSerializer,
    AgentSFDAdminSerializer,
    SuperviseurSFDAdminSerializer,
    AdministrateurSFDAdminSerializer,
    AdminPlateformeAdminSerializer,
    SFDSerializer,
)
from .permissions import IsAdminPlateformeOrSuperuser
from .models import AgentSFD, SuperviseurSFD, AdministrateurSFD, AdminPlateforme, SFD

# Create your views here.

@extend_schema(
    summary="Inscription d'un client (visiteur)",
    description="Permet à un visiteur de créer un compte CLIENT. Champs requis : nom, prenom, telephone, email, adresse, profession, motDePasse, pieceIdentite, photoIdentite.",
    request=InscriptionSerializer,
    responses={201: None, 400: None},
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
@extend_schema(
    tags=["👥 Gestion des Agents"],
    summary="CRUD Agents SFD",
    description="Créer, lister, modifier ou supprimer un agent SFD. POST: nom, prenom, telephone, email, adresse, profession, motDePasse, sfd_id, est_actif. Retourne l'agent créé avec info SFD.",
    request=AgentSFDAdminSerializer,
    responses={201: AgentSFDAdminSerializer, 200: AgentSFDAdminSerializer},
    examples=[
        OpenApiExample(
            'Exemple création agent SFD',
            value={
                "nom": "Dupont",
                "prenom": "Jean",
                "email": "jean@sfd.com",
                "telephone": "+22967123456",
                "motDePasse": "motdepasse123",
                "adresse": "Cotonou",
                "profession": "Agent",
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

@extend_schema(
    tags=["👥 Gestion des Superviseurs"],
    summary="CRUD Superviseurs SFD",
    description="Créer, lister, modifier ou supprimer un superviseur SFD. POST: nom, prenom, telephone, email, adresse, profession, motDePasse, sfd_id, est_actif. Retourne le superviseur créé avec info SFD.",
    request=SuperviseurSFDAdminSerializer,
    responses={201: SuperviseurSFDAdminSerializer, 200: SuperviseurSFDAdminSerializer},
    examples=[
        OpenApiExample(
            'Exemple création superviseur SFD',
            value={
                "nom": "Smith",
                "prenom": "Anna",
                "email": "anna@sfd.com",
                "telephone": "+22967123457",
                "motDePasse": "motdepasse456",
                "adresse": "Porto-Novo",
                "profession": "Superviseur",
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

@extend_schema(
    tags=["👥 Gestion des Admin SFD"],
    summary="CRUD Administrateurs SFD",
    description="Créer, lister, modifier ou supprimer un administrateur SFD. POST: nom, prenom, telephone, email, adresse, profession, motDePasse, sfd_id, peut_creer_tontines, est_actif. Retourne l'administrateur créé avec info SFD.",
    request=AdministrateurSFDAdminSerializer,
    responses={201: AdministrateurSFDAdminSerializer, 200: AdministrateurSFDAdminSerializer},
    examples=[
        OpenApiExample(
            'Exemple création administrateur SFD',
            value={
                "nom": "Kouassi",
                "prenom": "Paul",
                "email": "paul@sfd.com",
                "telephone": "+22967123458",
                "motDePasse": "motdepasse789",
                "adresse": "Parakou",
                "profession": "Admin",
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

@extend_schema(
    tags=["👥 Gestion des Admin Plateforme"],
    summary="CRUD Admins Plateforme",
    description="Créer, lister, modifier ou supprimer un admin plateforme. POST: nom, prenom, telephone, email, adresse, profession, motDePasse, peut_gerer_comptes, peut_gerer_sfd, est_actif. Retourne l'admin plateforme créé.",
    request=AdminPlateformeAdminSerializer,
    responses={201: AdminPlateformeAdminSerializer, 200: AdminPlateformeAdminSerializer},
    examples=[
        OpenApiExample(
            'Exemple création admin plateforme',
            value={
                "nom": "Tonti",
                "prenom": "Flex",
                "email": "admin@tontiflex.com",
                "telephone": "+22967123459",
                "motDePasse": "motdepasseadmin",
                "adresse": "Abomey",
                "profession": "SuperAdmin",
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

@extend_schema(
    summary="CRUD SFD (Structures Financières Décentralisées)",
    description="Gestion complète des SFD - réservé aux AdminPlateforme",
    tags=["🏢 Gestion SFD"]
)
class SFDViewSet(viewsets.ModelViewSet):
    queryset = SFD.objects.all()
    serializer_class = SFDSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminPlateformeOrSuperuser]

# Alias for JWT login and refresh
@extend_schema(
    summary="Connexion JWT (login)",
    description="Authentification JWT. Champs : email, motDePasse. Renvoie access et refresh token.",
)
class LoginView(TokenObtainPairView):
    """
    POST /api/auth/login/
    """
    permission_classes = [permissions.AllowAny]

@extend_schema(
    summary="Rafraîchissement du token JWT",
    description="Renvoie un nouveau access token à partir d'un refresh token JWT.",
)
class TokenRefreshViewCustom(TokenRefreshView):
    """
    POST /api/auth/token/refresh/
    """
    permission_classes = [permissions.AllowAny]
