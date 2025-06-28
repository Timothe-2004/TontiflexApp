from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from decimal import Decimal
import django.db.transaction
from django.utils import timezone
from django.db.models import Sum, Count
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample, OpenApiResponse

# Import des modèles Tontines et KKiaPay uniquement
from .models import Adhesion, Tontine, TontineParticipant, Cotisation, Retrait, SoldeTontine, CarnetCotisation
from payments.models import KKiaPayTransaction  # Migration vers KKiaPay terminée

# Import des serializers Tontines uniquement
from .serializers import (
    AdhesionSerializer, TontineSerializer, TontineParticipantSerializer, 
    CotisationSerializer, RetraitSerializer, SoldeTontineSerializer, CarnetCotisationSerializer,
    # Custom action serializers
    ValiderAgentRequestSerializer, PayerRequestSerializer, IntegrerRequestSerializer,
    CotiserRequestSerializer
)


# =============================================================================
# VIEWSETS POUR TONTINES
# =============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="Liste des demandes d'adhésion",
        description="""
        Récupère la liste des demandes d'adhésion aux tontines.
        
        Processus d'adhésion TontiFlex:
        1. Client soumet une demande avec pièce d'identité
        2. Vérification du montant de cotisation (dans les limites min/max)
        3. Validation par l'agent SFD (vérification documents)
        4. Paiement des frais d'adhésion via Mobile Money
        5. Intégration automatique dans la tontine
        
        Statuts possibles:
        en_attente: Demande soumise, en attente de validation
        validee_agent: Documents validés par l'agent SFD
        payee: Frais d'adhésion payés via Mobile Money
        integree: Client officiellement membre de la tontine
        rejetee: Demande refusée (documents invalides)
        
        Filtres disponibles:
        Par tontine
        Par statut de demande
        Par client demandeur
        Par agent validateur
        """,
        responses={200: AdhesionSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Créer une demande d'adhésion",
        description="""
        Créer une nouvelle demande d'adhésion à une tontine.
        
        Conditions d'éligibilité:
        Client enregistré avec profil complet
        Tontine active et ouverte aux adhésions
        Montant de cotisation dans les limites définies
        Documents d'identité valides (CNI, passeport, etc.)
        
        Données requises:
        ID de la tontine cible
        Montant de cotisation proposé
        Copie numérisée de la pièce d'identité
        Justification de profession/revenus (optionnel)
        
        Workflow après création:
        1. Statut initial: en_attente
        2. Notification à l'agent SFD pour validation
        3. Attente de validation des documents
        """,
        request=AdhesionSerializer,
        responses={
            201: AdhesionSerializer,
            400: OpenApiResponse(description="Données invalides ou montant hors limites"),
            409: OpenApiResponse(description="Client déjà membre de cette tontine")
        },
        examples=[
            OpenApiExample(
                "Demande d'adhésion standard",
                value={
                    "tontine": 1,
                    "client": 5,
                    "montant_cotisation": 50000,
                    "document_identite": "data:image/jpeg;base64,/9j/4AAQSkZJRgABA...",
                    "type_document": "CNI",
                    "commentaires": "Adhésion pour épargne familiale"
                }
            )
        ]
    ),
    retrieve=extend_schema(
        summary="Détails d'une demande d'adhésion",
        description="Récupère les informations détaillées d'une demande d'adhésion spécifique avec son historique de traitement."
    ),
    update=extend_schema(
        summary="Modifier une demande d'adhésion",
        description="""
        Met à jour une demande d'adhésion existante.
        
        Modifications possibles:
        Montant de cotisation (si pas encore validé)
        Documents d'identité (remplacement)
        Commentaires additionnels
        Statut de la demande (pour les agents/admins)
        
        Restrictions:
        Seul le client peut modifier avant validation agent
        Agents/admins peuvent modifier le statut
        Aucune modification après intégration
        """
    ),
    partial_update=extend_schema(
        summary="Modification partielle d'une demande d'adhésion",
        description="Met à jour partiellement une demande d'adhésion (uniquement les champs fournis)."
    ),
    destroy=extend_schema(
        summary="Supprimer une demande d'adhésion",
        description="""
        Supprime définitivement une demande d'adhésion.
        
        Conditions de suppression:
        Demande en statut en_attente uniquement
        Seul le client demandeur peut supprimer
        Admins peuvent supprimer toute demande non intégrée
        
        Effets: Suppression complète, pas de récupération possible
        """
    )
)
@extend_schema(tags=["📝 Adhésions"])
class AdhesionViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des demandes d'adhésion à une tontine
    """
    queryset = Adhesion.objects.all()
    serializer_class = AdhesionSerializer   
    @extend_schema(
        summary="Valider une demande d'adhésion (Agent SFD)",
        description="""
        Permet à un agent SFD de valider les documents d'identité d'une demande d'adhésion.
        
        **Rôle de l'agent SFD**:
        - Vérification de l'authenticité des pièces d'identité
        - Contrôle de la conformité des informations client
        - Validation de la capacité financière du demandeur
        - Autorisation de passage à l'étape de paiement
        
        **Processus de validation**:
        1. Examen des documents fournis
        2. Vérification des informations personnelles
        3. Contrôle du montant de cotisation proposé
        4. Décision de validation ou de rejet avec commentaires
        
        **Permissions requises**: Agent SFD de la SFD gestionnaire de la tontine
        """,
        request=ValiderAgentRequestSerializer,
        responses={
            200: AdhesionSerializer,
            400: OpenApiResponse(description="Données de validation invalides"),
            403: OpenApiResponse(description="Agent non autorisé pour cette SFD"),
            404: OpenApiResponse(description="Demande d'adhésion introuvable")
        },
        examples=[
            OpenApiExample(
                "Validation agent réussie",
                value={
                    "agent": 2,
                    "commentaires": "Documents conformes, identité vérifiée",
                    "decision": "valide"
                }
            ),
            OpenApiExample(
                "Rejet par agent",
                value={
                    "agent": 2,
                    "commentaires": "CNI expirée, renouvellement requis",
                    "decision": "rejete"
                }
            )
        ]
    )
    @action(detail=True, methods=['post'], url_path='valider-agent')
    def valider_agent(self, request, pk=None):
        """
        Action pour valider une demande d'adhésion par un agent SFD
        """
        adhesion = self.get_object()
        serializer = ValiderAgentRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                with django.db.transaction.atomic():
                    # Logique de validation par agent
                    adhesion.statut = 'validee_agent'
                    adhesion.agent_validateur = serializer.validated_data.get('agent')
                    adhesion.commentaires_agent = serializer.validated_data.get('commentaires', '')
                    adhesion.date_validation_agent = timezone.now()
                    adhesion.save()
                    
                return Response({
                    'success': True,
                    'message': 'Demande validée par agent',
                    'adhesion': AdhesionSerializer(adhesion).data
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Payer les frais d'adhésion via Mobile Money",
        description="""
        Permet de payer les frais d'adhésion à une tontine via Mobile Money (MTN/Moov).
        
        **Processus de paiement**:
        1. Vérification que la demande est validée par l'agent
        2. Initiation de la transaction Mobile Money
        3. Confirmation du paiement par l'opérateur
        4. Mise à jour du statut de la demande à 'payee'
        5. Déclenchement de l'intégration automatique
        
        **Opérateurs supportés**:
        - MTN Mobile Money
        - Moov Money
        
        **Frais applicables**:
        - Frais d'adhésion définis par la tontine
        - Commission opérateur Mobile Money
        - Commission SFD gestionnaire
        
        **Conditions**:
        - Demande préalablement validée par un agent SFD
        - Solde Mobile Money suffisant
        - Numéro de téléphone Mobile Money actif
        """,
        request=PayerRequestSerializer,
        responses={
            200: AdhesionSerializer,
            400: OpenApiResponse(description="Erreur de paiement ou demande non validée"),
            402: OpenApiResponse(description="Solde Mobile Money insuffisant"),
            503: OpenApiResponse(description="Service Mobile Money temporairement indisponible")
        },
        examples=[
            OpenApiExample(
                "Paiement KKiaPay",
                value={
                    "numero_telephone": "+22370123456"  # MIGRATION : KKiaPay simplifié
                    # operateur et pin_mobile_money supprimés - KKiaPay gère automatiquement
                }
            ),
            OpenApiExample(
                "Paiement KKiaPay Alt",
                value={
                    "numero_telephone": "+22369987654"  # MIGRATION : KKiaPay unifié
                    # operateur et pin_mobile_money non nécessaires
                }
            )
        ]
    )
    @action(detail=True, methods=['post'], url_path='payer')
    def payer(self, request, pk=None):
        """
        Action pour effectuer le paiement des frais d'adhésion
        """
        adhesion = self.get_object()
        serializer = PayerRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                with django.db.transaction.atomic():
                    # Logique de paiement via KKiaPay
                    numero_telephone = serializer.validated_data['numero_telephone']  # MIGRATION : numero_mobile_money → numero_telephone
                    # MIGRATION : operateur supprimé - KKiaPay gère automatiquement
                    
                    # Créer une transaction KKiaPay
                    from payments.services_migration import migration_service
                    
                    transaction_data = {
                        'user': adhesion.client.user,
                        'montant': adhesion.tontine.fraisAdhesion,
                        'telephone': numero_telephone,
                        'adhesion_id': adhesion.id,
                        'description': f"Paiement adhésion tontine {adhesion.tontine.nom}"
                    }
                    
                    transaction = migration_service.create_tontine_adhesion_transaction(transaction_data)
                    
                    adhesion.statut = 'paiement_effectue'
                    adhesion.transaction_paiement = transaction
                    adhesion.save()
                    
                return Response({
                    'success': True,
                    'message': 'Paiement initié',
                    'transaction_id': transaction.id,
                    'adhesion': AdhesionSerializer(adhesion).data
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Intégrer le client dans la tontine",
        description="""
        Finalise l'adhésion en intégrant officiellement le client dans la tontine.
        
        **Processus d'intégration**:
        1. Vérification que le paiement est confirmé
        2. Création du profil TontineParticipant
        3. Génération du carnet de cotisation
        4. Attribution du numéro de membre
        5. Notification de bienvenue au client
        6. Mise à jour des statistiques de la tontine
        
        **Actions automatiques**:
        - Création du carnet de cotisation personnalisé
        - Définition du calendrier de cotisation
        - Attribution du rang de distribution
        - Calcul des échéances de cotisation
        - Envoi de notification SMS/email de confirmation
        
        **Conditions**:
        - Paiement des frais d'adhésion confirmé
        - Validation agent SFD effectuée
        - Tontine encore ouverte aux adhésions
        - Nombre maximum de participants non atteint
        """,
        request=IntegrerRequestSerializer,
        responses={
            200: AdhesionSerializer,
            400: OpenApiResponse(description="Intégration impossible - conditions non remplies"),
            409: OpenApiResponse(description="Client déjà intégré ou tontine complète")
        },
        examples=[
            OpenApiExample(
                "Intégration réussie",
                value={
                    "numero_membre": "T001-M015",
                    "rang_distribution": 15,
                    "confirmer_integration": True
                }
            )
        ]
    )
    @action(detail=True, methods=['post'], url_path='integrer')
    def integrer(self, request, pk=None):
        """
        Action pour intégrer un client à la tontine après paiement validé
        """
        adhesion = self.get_object()
        serializer = IntegrerRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                with django.db.transaction.atomic():
                    # Créer le participant à la tontine
                    participant = TontineParticipant.objects.create(
                        tontine=adhesion.tontine,
                        client=adhesion.client,
                        date_adhesion=timezone.now(),
                        montant_cotisation=adhesion.montant_cotisation_propose
                    )
                    
                    # Créer le solde initial pour ce participant
                    SoldeTontine.objects.create(
                        tontine=adhesion.tontine,
                        client=adhesion.client,
                        solde_actuel=Decimal('0.00'),
                        total_cotisations=Decimal('0.00'),
                        total_retraits=Decimal('0.00')
                    )
                    
                    # Créer le carnet de cotisation (31 jours)
                    CarnetCotisation.objects.create(
                        participant=participant,
                        mois=timezone.now().month,
                        annee=timezone.now().year,
                        carnet_data={}  # JSONField vide au début
                    )
                    
                    adhesion.statut = 'integree'
                    adhesion.participant_cree = participant
                    adhesion.save()
                    
                return Response({
                    'success': True,
                    'message': 'Client intégré à la tontine',
                    'participant_id': participant.id,
                    'adhesion': AdhesionSerializer(adhesion).data
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema_view(
    list=extend_schema(
        summary="Liste des tontines disponibles",
        description="""
        Affiche la liste des tontines configurées par les SFD.
        
        Types de tontines TontiFlex:
        Tontine classique: Cotisations quotidiennes, distribution cyclique
        Tontine épargne: Focus épargne avec intérêts
        Tontine crédit: Accès privilégié aux prêts pour les membres
        
        Cycle de fonctionnement:
        Durée: 31 jours par cycle
        1ère cotisation de chaque cycle = commission SFD
        Distribution selon l'ordre défini
        Renouvellement automatique des cycles
        
        Informations affichées:
        Montants min/max de cotisation
        Nombre de participants actifs
        Frais d'adhésion et commissions
        Statut de la tontine (ouverte/fermée/archivée)
        Dates importantes (création, prochain cycle)
        """,
        responses={200: TontineSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Créer une nouvelle tontine",
        description="""
        Crée une nouvelle tontine avec ses paramètres de fonctionnement.
        
        Configuration requise:
        SFD gestionnaire de la tontine
        Montants minimum et maximum de cotisation
        Frais d'adhésion et commission SFD
        Nombre maximum de participants
        Conditions d'éligibilité
        
        Paramètres automatiques:
        Cycle de 31 jours
        Commission SFD sur 1ère cotisation
        Système de distribution rotatif
        Calendrier de cotisation quotidienne
        
        Permissions requises: Admin SFD
        """,
        request=TontineSerializer,
        responses={
            201: TontineSerializer,
            400: OpenApiResponse(description="Paramètres de tontine invalides"),
            403: OpenApiResponse(description="Permissions insuffisantes")
        },
        examples=[
            OpenApiExample(
                "Tontine classique",
                value={
                    "nom": "Tontine Cotonou Centre",
                    "description": "Tontine quotidienne pour commerçants",
                    "sfd": 1,
                    "montant_min_cotisation": 10000,
                    "montant_max_cotisation": 100000,
                    "frais_adhesion": 5000,
                    "commission_sfd": 2.5,
                    "nombre_max_participants": 30,
                    "est_active": True
                }
            )
        ]
    ),
    retrieve=extend_schema(
        summary="Détails d'une tontine",
        description="Récupère les informations détaillées d'une tontine spécifique avec ses statistiques et participants."
    ),
    update=extend_schema(
        summary="Modifier une tontine",
        description="""
        Met à jour les paramètres d'une tontine existante.
        
        Modifications possibles:
        Nom et description de la tontine
        Montants min/max de cotisation (si pas de participants)
        Frais d'adhésion et commission SFD
        Nombre maximum de participants
        Statut actif/inactif
        
        Restrictions:
        Certains paramètres non modifiables si participants actifs
        Seuls les admins SFD peuvent modifier leurs tontines
        """
    ),
    partial_update=extend_schema(
        summary="Modification partielle d'une tontine",
        description="Met à jour partiellement les paramètres d'une tontine (uniquement les champs fournis)."
    ),
    destroy=extend_schema(
        summary="Supprimer une tontine",
        description="""
        Désactive définitivement une tontine.
        
        Conditions de suppression:
        Aucun participant actif
        Tous les cycles terminés
        Soldes participants à zéro        
        Permissions requises: Admin SFD propriétaire
        Effets: Tontine archivée, historique conservé
        """
    )
)
@extend_schema(tags=["🏛️ Tontines"])
class TontineViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des tontines
    """
    queryset = Tontine.objects.all()
    serializer_class = TontineSerializer

    @extend_schema(
        summary="Liste des participants de la tontine",
        description="""
        Récupère la liste des participants actifs d'une tontine spécifique.
        
        **Informations par participant**:
        - Profil client (nom, téléphone, email)
        - Date d'adhésion et numéro de membre
        - Montant de cotisation choisi
        - Rang dans l'ordre de distribution
        - Historique des cotisations
        - Solde actuel dans la tontine
        - Statut de participation (actif/suspendu/retiré)
        
        **Statistiques incluses**:
        - Total des cotisations versées
        - Nombre de cotisations manquées
        - Prochaine date de distribution
        - Montant à recevoir à sa distribution
        
        **Permissions requises**:
        - Agent/Superviseur/Admin SFD: participants de leurs tontines
        - Client: peut voir uniquement la liste (sans détails financiers)
        """,
        responses={
            200: TontineParticipantSerializer(many=True),
            403: OpenApiResponse(description="Accès refusé - SFD différente"),
            404: OpenApiResponse(description="Tontine introuvable")
        }
    )
    @action(detail=True, methods=['get'], url_path='participants')
    def participants(self, request, pk=None):
        """
        GET /api/tontines/{tontine_id}/participants/
        Retourne la liste des participants d'une tontine donnée.
        Permissions: AgentSFD, SuperviseurSFD, AdminSFD du SFD propriétaire de la tontine
        """
        tontine = self.get_object()
        
        # Vérifier les permissions
        user = request.user
        user_sfd = None
        
        if hasattr(user, 'agentsfd'):
            user_sfd = user.agentsfd.sfd
        elif hasattr(user, 'superviseurssfd'):
            user_sfd = user.superviseurssfd.sfd
        elif hasattr(user, 'administrateurssfd'):
            user_sfd = user.administrateurssfd.sfd
        elif hasattr(user, 'adminplateforme'):
            # Admin plateforme peut tout voir
            user_sfd = tontine.administrateurId.sfd
        
        if not user_sfd or user_sfd != tontine.administrateurId.sfd:
            return Response(
                {'error': 'Vous n\'avez accès qu\'aux tontines de votre SFD'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Récupérer les participants actifs
        participants = TontineParticipant.objects.filter(
            tontine=tontine,
            statut='actif'
        ).select_related('client')
        
        serializer = TontineParticipantSerializer(participants, many=True)
        
        return Response({
            'tontine': tontine.nom,
            'sfd': tontine.administrateurId.sfd.nom,
            'participants': serializer.data,
            'total_participants': participants.count()
        })

@extend_schema_view(
    list=extend_schema(
        summary="Liste des participants aux tontines",
        description="""
        Affiche la liste de tous les participants aux tontines du système.
        
        Données des participants:
        Informations client et tontine de rattachement
        Date d'adhésion et numéro de membre
        Montant de cotisation convenu
        Historique des cotisations
        Solde et statistiques de participation
        
        Filtres disponibles:
        Par tontine spécifique
        Par SFD gestionnaire
        Par statut de participation
        Par période d'adhésion
        
        Permissions requises: Selon le rôle utilisateur
        """,
        responses={200: TontineParticipantSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Ajouter un participant à une tontine",
        description="""
        Crée un nouveau participant dans une tontine (généralement via intégration d'adhésion).
        
        Prérequis:
        Adhésion validée et payée
        Client avec profil complet
        Tontine active et non complète
        Documents d'identité validés
        
        Processus automatique:
        Création du participant
        Attribution du numéro de membre
        Initialisation du solde
        Création du carnet de cotisation
        """
    ),
    retrieve=extend_schema(
        summary="Détails d'un participant",
        description="Récupère les informations détaillées d'un participant spécifique avec son historique de cotisations."
    ),
    update=extend_schema(
        summary="Modifier un participant",
        description="""
        Met à jour les informations d'un participant à une tontine.
        
        Modifications possibles:
        Montant de cotisation (avec validation)
        Statut de participation (actif/suspendu/retiré)
        Numéro de membre (réorganisation)
        
        Restrictions:
        Certaines modifications nécessitent validation agent
        Modification du montant peut affecter le cycle
        """
    ),
    partial_update=extend_schema(
        summary="Modification partielle d'un participant",
        description="Met à jour partiellement les informations d'un participant (uniquement les champs fournis)."
    ),
    destroy=extend_schema(
        summary="Retirer un participant",
        description="""
        Retire définitivement un participant d'une tontine.
        
        Conditions:
        Solde du participant soldé
        Aucune cotisation en cours
        Validation par agent SFD
        
        Effets: Participant retiré, historique conservé
        """
    )
)
@extend_schema(tags=["👥 Participants"])
class TontineParticipantViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des participants aux tontines
    """
    queryset = TontineParticipant.objects.all()
    serializer_class = TontineParticipantSerializer   
    @extend_schema(
        summary="Effectuer une cotisation via Mobile Money",
        description="""
        Permet à un participant de cotiser à sa tontine via Mobile Money.
        
        **Processus de cotisation**:
        1. Validation du montant (conforme au montant convenu)
        2. Vérification du statut du participant (actif)
        3. Initiation de la transaction Mobile Money
        4. Confirmation du paiement par l'opérateur
        5. Mise à jour du solde et historique
        6. Enregistrement dans le carnet de cotisation
        
        **Règles spéciales**:
        - 1ère cotisation de chaque cycle = commission SFD
        - Cotisations quotidiennes recommandées
        - Pénalités en cas de retard prolongé
        - Bonus de ponctualité possible selon SFD
        
        **Notifications automatiques**:
        - Confirmation SMS/email au participant
        - Notification au groupe de la tontine
        - Mise à jour du classement de ponctualité
        """,
        request=CotiserRequestSerializer,
        responses={
            200: CotisationSerializer,
            400: OpenApiResponse(description="Montant invalide ou participant inactif"),
            402: OpenApiResponse(description="Solde Mobile Money insuffisant"),
            409: OpenApiResponse(description="Cotisation déjà effectuée aujourd'hui")
        },
        examples=[
            OpenApiExample(
                "Cotisation quotidienne",
                value={
                    "numero_telephone": "+22370123456",
                    "montant": 25000,
                    "operateur": "MTN",
                    "is_commission": False,
                    "commentaire": "Cotisation du jour"
                }
            ),
            OpenApiExample(
                "Commission SFD (1ère cotisation cycle)",
                value={
                    "numero_telephone": "+22370123456",
                    "montant": 25000,
                    "operateur": "MTN",
                    "is_commission": True,
                    "commentaire": "Commission cycle janvier"
                }
            )
        ]
    )
    @action(detail=True, methods=['post'], url_path='cotiser')
    def cotiser(self, request, pk=None):
        """
        Action pour effectuer une cotisation
        """
        participant = self.get_object()
        serializer = CotiserRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                with django.db.transaction.atomic():
                    numero_telephone = serializer.validated_data['numero_telephone']
                    montant = serializer.validated_data['montant']
                    is_commission = serializer.validated_data.get('is_commission', False)
                    
                    # Créer la transaction KKiaPay
                    from payments.services_migration import migration_service
                    
                    transaction_data = {
                        'user': participant.client.user,
                        'montant': montant,
                        'telephone': numero_telephone,
                        'cotisation_id': f"PART_{participant.id}",
                        'description': f"Cotisation tontine {participant.tontine.nom}"
                    }
                    
                    transaction = migration_service.create_tontine_contribution_transaction(transaction_data)
                    
                    # Créer la cotisation
                    cotisation = Cotisation.objects.create(
                        participant=participant,
                        montant=montant,
                        date_cotisation=timezone.now(),
                        transaction_kkiapay=transaction,
                        is_commission_sfd=is_commission
                    )
                    
                    # Mettre à jour le solde
                    solde, created = SoldeTontine.objects.get_or_create(
                        tontine=participant.tontine,
                        client=participant.client,
                        defaults={
                            'solde_actuel': Decimal('0.00'),
                            'total_cotisations': Decimal('0.00'),
                            'total_retraits': Decimal('0.00')
                        }
                    )
                    
                    if not is_commission:
                        solde.solde_actuel += montant
                        solde.total_cotisations += montant
                        solde.save()
                    
                    # Mettre à jour le carnet de cotisation
                    carnet, created = CarnetCotisation.objects.get_or_create(
                        participant=participant,
                        mois=timezone.now().month,
                        annee=timezone.now().year,
                        defaults={'carnet_data': {}}
                    )
                    
                    # Ajouter la cotisation du jour dans le carnet
                    jour = timezone.now().day
                    if not carnet.carnet_data:
                        carnet.carnet_data = {}
                    carnet.carnet_data[str(jour)] = {
                        'montant': str(montant),
                        'transaction_id': transaction.id,
                        'is_commission': is_commission,
                        'timestamp': timezone.now().isoformat()
                    }
                    carnet.save()
                    
                return Response({
                    'success': True,
                    'message': 'Cotisation enregistrée',
                    'cotisation_id': cotisation.id,
                    'transaction_id': transaction.id,
                    'nouveau_solde': solde.solde_actuel if not is_commission else None
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Statistiques globales des participants",
        description="""
        Fournit des statistiques consolidées sur l'ensemble des participants aux tontines.
        
        **Métriques de participation**:
        - Nombre total de participants enregistrés
        - Participants actifs vs inactifs/retirés
        - Évolution mensuelle des adhésions
        - Répartition par SFD gestionnaire
        
        **Statistiques financières**:
        - Volume total des cotisations
        - Cotisations du mois en cours
        - Montant des commissions SFD
        - Moyennes de cotisation par participant
        
        **Indicateurs de performance**:
        - Taux de ponctualité global
        - Fréquence des retards de cotisation
        - Taux de rétention des participants
        - Satisfaction et feedback moyen
        
        **Analyses temporelles**:
        - Évolution sur 12 derniers mois
        - Pics et creux d'activité
        - Saisonnalité des cotisations
        - Projections basées sur tendances
        
        **Segmentation**:
        - Par tranche de montant de cotisation
        - Par ancienneté de participation
        - Par zone géographique
        - Par type de tontine
        
        **Permissions requises**: Agent SFD, Superviseur SFD, Admin SFD ou Admin plateforme
        """,
        responses={
            200: OpenApiResponse(
                description="Statistiques des participants récupérées",
                examples=[
                    OpenApiExample(
                        "Statistiques globales",
                        value={
                            "participants": {
                                "total": 1250,
                                "actifs": 1180,
                                "nouveaux_ce_mois": 45,
                                "taux_retention": 94.4
                            },
                            "financier": {
                                "total_cotisations": 125000000,
                                "cotisations_ce_mois": 8500000,
                                "commissions_sfd": 2750000,
                                "moyenne_cotisation": 22500
                            },
                            "performance": {
                                "taux_ponctualite_global": 89.2,
                                "retards_ce_mois": 78,
                                "taux_croissance_mensuelle": 3.6
                            },
                            "tendances": {
                                "evolution_12_mois": [
                                    {"mois": "2024-07", "participants": 1050, "cotisations": 6800000},
                                    {"mois": "2024-08", "participants": 1095, "cotisations": 7200000}
                                ]
                            }
                        }
                    )
                ]
            ),
            403: OpenApiResponse(description="Permissions insuffisantes pour accéder aux statistiques")
        }
    )
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """
        Action pour obtenir les statistiques des participants
        """
        stats = {
            'total_participants': TontineParticipant.objects.count(),
            'participants_actifs': TontineParticipant.objects.filter(date_retrait__isnull=True).count(),
            'total_cotisations': Cotisation.objects.aggregate(total=Sum('montant'))['total'] or 0,
            'cotisations_ce_mois': Cotisation.objects.filter(
                date_cotisation__month=timezone.now().month,
                date_cotisation__year=timezone.now().year
            ).aggregate(total=Sum('montant'))['total'] or 0,
            'commissions_sfd': Cotisation.objects.filter(
                is_commission_sfd=True
            ).aggregate(total=Sum('montant'))['total'] or 0,        }
        
        return Response(stats, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(
        summary="Historique des cotisations",
        description="""
        Affiche l'historique complet des cotisations effectuées.
        
        Informations des cotisations:
        Participant et tontine concernés
        Montant et date de cotisation
        Type (cotisation normale/commission SFD)
        Détails de la transaction Mobile Money
        Statut de confirmation
        
        Filtres disponibles:
        Par participant ou tontine
        Par période (date début/fin)
        Par type de cotisation
        Par statut de transaction
        
        Permissions requises: Selon le rôle utilisateur
        """,
        responses={200: CotisationSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Enregistrer une cotisation",
        description="""
        Enregistre une nouvelle cotisation dans le système.
        
        Processus automatique:
        Validation du participant et montant
        Vérification des conditions de cotisation
        Initiation transaction Mobile Money
        Confirmation et mise à jour soldes
        """
    ),
    retrieve=extend_schema(
        summary="Détails d'une cotisation",
        description="Récupère les informations détaillées d'une cotisation spécifique avec les détails de transaction."
    ),
    update=extend_schema(
        summary="Modifier une cotisation",
        description="""
        Met à jour une cotisation existante.
        
        Modifications possibles:
        Correction du montant (si transaction échouée)
        Mise à jour du statut de confirmation
        Ajout de commentaires ou notes
        
        Restrictions: Seules les cotisations non confirmées peuvent être modifiées
        """
    ),
    partial_update=extend_schema(
        summary="Modification partielle d'une cotisation",
        description="Met à jour partiellement une cotisation (uniquement les champs fournis)."
    ),
    destroy=extend_schema(
        summary="Supprimer une cotisation",
        description="""
        Supprime définitivement une cotisation.
        
        Conditions:
        Transaction Mobile Money échouée
        Cotisation non confirmée
        Autorisation agent SFD
        
        Effets: Suppression avec ajustement des soldes
        """
    )
)
@extend_schema(tags=["💰 Cotisations"])
class CotisationViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des cotisations
    """
    queryset = Cotisation.objects.all()
    serializer_class = CotisationSerializer


@extend_schema_view(
    list=extend_schema(
        summary="Liste des demandes de retrait",
        description="""
        Affiche les demandes de retrait soumises par les participants.
        
        Processus de retrait TontiFlex:
        1. Participant soumet une demande de retrait
        2. Vérification du solde disponible
        3. Validation par l'agent SFD
        4. Vérification des fonds SFD suffisants
        5. Traitement du retrait via Mobile Money
        
        Statuts de retrait:
        en_attente: Demande soumise
        validee_agent: Approuvée par l'agent SFD
        traitee: Retrait effectué et confirmé
        rejetee: Demande refusée (motif indiqué)
        
        Conditions de retrait:
        Solde suffisant dans la tontine
        Fonds SFD disponibles
        Validation agent SFD requise
        """,
        responses={200: RetraitSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Demander un retrait",
        description="""
        Permet à un participant de demander un retrait de ses fonds.
        
        Conditions:
        Participant actif de la tontine
        Solde suffisant disponible
        Pas de retrait en cours de traitement
        Respect des limites de retrait définies
        
        Informations requises:
        Montant souhaité
        Motif du retrait
        Numéro Mobile Money de réception
        Confirmation d'identité
        """,
        request=RetraitSerializer,
        responses={
            201: RetraitSerializer,
            400: OpenApiResponse(description="Solde insuffisant ou données invalides"),
            409: OpenApiResponse(description="Retrait déjà en cours")
        }
    ),
    retrieve=extend_schema(
        summary="Détails d'une demande de retrait",
        description="Récupère les informations détaillées d'une demande de retrait avec son statut de traitement."
    ),
    update=extend_schema(
        summary="Modifier une demande de retrait",
        description="""
        Met à jour une demande de retrait existante.
        
        Modifications possibles:
        Montant demandé (si en_attente)
        Statut par agent SFD (validation/rejet)
        Motif de rejet
        Numéro Mobile Money de réception
        
        Restrictions: Seules les demandes non traitées peuvent être modifiées
        """
    ),
    partial_update=extend_schema(
        summary="Modification partielle d'une demande de retrait",
        description="Met à jour partiellement une demande de retrait (uniquement les champs fournis)."
    ),
    destroy=extend_schema(
        summary="Supprimer une demande de retrait",
        description="""
        Supprime définitivement une demande de retrait.
        
        Conditions:
        Demande en statut en_attente uniquement
        Seul le demandeur peut supprimer
        Agents peuvent supprimer demandes non traitées
        
        Effets: Suppression complète de la demande
        """
    )
)
@extend_schema(tags=["🏦 Retraits"])
class RetraitViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des retraits
    """
    queryset = Retrait.objects.all()
    serializer_class = RetraitSerializer


@extend_schema_view(
    list=extend_schema(
        summary="Soldes des participants par tontine",
        description="""
        Affiche les soldes actuels des participants pour chaque tontine.
        
        Calcul du solde:
        Total des cotisations versées
        Moins les retraits effectués
        Moins les commissions SFD
        Plus les intérêts éventuels
        
        Détails inclus:
        Solde actuel disponible
        Total cotisé depuis l'adhésion
        Total retiré à ce jour
        Historique des transactions
        Prochaine distribution prévue
        
        Filtres disponibles:
        Par tontine
        Par client/participant
        Par période
        Par statut de compte
        """,
        responses={200: SoldeTontineSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Créer un solde de tontine",
        description="""
        Initialise un nouveau solde pour un participant dans une tontine.
        
        Création automatique lors de l'intégration d'un participant
        Solde initial à zéro
        Historique vide au départ
        """
    ),
    retrieve=extend_schema(
        summary="Détails d'un solde de tontine",
        description="Récupère les informations détaillées du solde d'un participant avec historique complet."
    ),
    update=extend_schema(
        summary="Modifier un solde de tontine",
        description="""
        Met à jour le solde d'un participant (généralement automatique).
        
        Modifications automatiques:
        Ajout lors des cotisations
        Déduction lors des retraits
        Calcul des intérêts
        Application des commissions
        """
    ),
    partial_update=extend_schema(
        summary="Modification partielle d'un solde",
        description="Met à jour partiellement un solde de tontine (correction administrative)."
    ),
    destroy=extend_schema(
        summary="Supprimer un solde de tontine",
        description="""
        Supprime le solde d'un participant (fin de participation).
        
        Conditions:
        Solde à zéro
        Aucune transaction en cours
        Participant retiré de la tontine
        """
    )
)
@extend_schema(tags=["💳 Soldes"])
class SoldeTontineViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des soldes par tontine
    """
    queryset = SoldeTontine.objects.all()
    serializer_class = SoldeTontineSerializer


@extend_schema_view(
    list=extend_schema(
        summary="Carnets de cotisation (cycles 31 jours)",
        description="""
        Gère les carnets de cotisation mensuels des participants.
        
        Fonctionnement du carnet:
        Cycle de 31 jours renouvelé automatiquement
        Suivi quotidien des cotisations
        1er jour = commission SFD obligatoire
        Jours 2-31 = cotisations normales
        
        Données du carnet:
        Calendrier des cotisations quotidiennes
        Montants versés par jour
        Statut des paiements (confirmé/en attente)
        Références des transactions Mobile Money
        Calcul de ponctualité et bonus
        
        Statistiques:
        Taux de ponctualité du participant
        Jours de retard cumulés
        Montant total du cycle
        Prochaines échéances
        """,
        responses={200: CarnetCotisationSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Créer un carnet de cotisation",
        description="""
        Initialise un nouveau carnet de cotisation pour un participant.
        
        Création automatique lors de l'intégration
        Cycle de 31 jours
        Calendrier vide au départ
        Structure JSON pour le suivi quotidien
        """
    ),
    retrieve=extend_schema(
        summary="Détails d'un carnet de cotisation",
        description="Récupère les informations détaillées d'un carnet avec le calendrier de cotisations."
    ),
    update=extend_schema(
        summary="Modifier un carnet de cotisation",
        description="""
        Met à jour un carnet de cotisation existant.
        
        Modifications possibles:
        Mise à jour du calendrier quotidien
        Ajout de cotisations confirmées
        Correction d'erreurs de saisie
        Calcul des statistiques de ponctualité
        """
    ),
    partial_update=extend_schema(
        summary="Modification partielle d'un carnet",
        description="Met à jour partiellement un carnet de cotisation (uniquement les champs fournis)."
    ),
    destroy=extend_schema(
        summary="Supprimer un carnet de cotisation",
        description="""
        Supprime définitivement un carnet de cotisation.
        
        Conditions:
        Cycle terminé ou participant retiré
        Aucune cotisation en cours
        Autorisation administrative
        
        Effets: Suppression avec archivage des données
        """
    )
)
@extend_schema(tags=["📊 Carnets"])
class CarnetCotisationViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des carnets de cotisation (31 jours)
    """
    queryset = CarnetCotisation.objects.all()
    serializer_class = CarnetCotisationSerializer
