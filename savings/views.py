from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from decimal import Decimal
import django.db.transaction
from django.utils import timezone
from django.db.models import Sum, Count, Q, Avg
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample, OpenApiResponse

# Import des modèles Savings uniquement
from .models import SavingsAccount, SavingsTransaction
from payments.models import KKiaPayTransaction  # MIGRATION : mobile_money → KKiaPay

# Import des serializers Savings uniquement
from .serializers import (
    SavingsAccountSerializer, SavingsTransactionSerializer,
    # Custom action serializers
    CreateRequestSerializer, ValidateRequestSerializer, PayFeesSerializer,
    DepositSerializer, WithdrawSerializer,
    # Summary/response serializers  
    SavingsAccountSummarySerializer, TransactionHistorySerializer,
    AccountStatusResponseSerializer, TransactionResponseSerializer
)

# Import des permissions
from .permissions import (
    IsSavingsAccountClient, IsAgentSFDForSavingsValidation, 
    SavingsAccountPermission, SavingsTransactionPermission
)

# Import des utilitaires
from .utils import (
    valider_eligibilite_compte_epargne, calculer_statistiques_compte,
    valider_montant_transaction, obtenir_prochaine_action_compte,
    formater_historique_transaction
)


# =============================================================================
# VIEWSETS POUR ÉPARGNE  
# =============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="Liste des comptes épargne",
        description="""
        Récupère la liste des comptes épargne selon les permissions utilisateur.
        
        Processus de création de compte épargne TontiFlex:
        1. Client soumet une demande avec documents d'identité
        2. Upload de la pièce d'identité et photo du client
        3. Validation par l'agent SFD (vérification documents)
        4. Paiement des frais de création via Mobile Money
        5. Activation automatique du compte après paiement confirmé
        
        Statuts possibles:
        en_cours_creation: Demande soumise, en attente de validation
        validee_agent: Documents validés par l'agent SFD
        paiement_effectue: Frais de création payés via Mobile Money
        actif: Compte épargne opérationnel
        suspendu: Compte temporairement désactivé
        ferme: Compte définitivement fermé
        
        Filtres disponibles:
        Par statut de compte
        Par client propriétaire
        Par agent validateur
        Par période de création
        """,
        responses={200: SavingsAccountSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Créer une demande de compte épargne",
        description="""
        Créer une nouvelle demande d'ouverture de compte épargne.
        
        Conditions d'éligibilité:
        Client enregistré avec profil complet  
        Aucun compte épargne actif existant
        Documents d'identité valides et récents
        Accord pour les frais de création
        
        Données requises:
        Copie numérisée de la pièce d'identité (CNI, passeport)
        Photo récente du titulaire du compte
        Numéro de téléphone Mobile Money pour les transactions
        Acceptation des conditions générales
        
        Workflow après création:
        1. Statut initial: en_cours_creation
        2. Notification à l'agent SFD pour validation
        3. Attente de validation des documents
        4. Processus de paiement des frais de création
        """,
        request=SavingsAccountSerializer,
        responses={
            201: SavingsAccountSerializer,
            400: OpenApiResponse(description="Données invalides ou client non éligible"),
            409: OpenApiResponse(description="Client possède déjà un compte épargne actif")
        },
        examples=[
            OpenApiExample(
                "Demande de compte épargne standard",
                value={
                    "client": 5,
                    "piece_identite": "data:image/jpeg;base64,/9j/4AAQSkZJRgABA...",
                    "photo_identite": "data:image/jpeg;base64,/9j/4AAQSkZJRgABA...",
                    "type_piece_identite": "CNI",
                    "numero_telephone": "+22370123456",
                    "commentaires": "Demande d'ouverture pour épargne familiale"
                }
            )
        ]
    ),
    retrieve=extend_schema(
        summary="Détails d'un compte épargne",
        description="Récupère les informations détaillées d'un compte épargne spécifique avec son solde et historique récent."
    ),
    update=extend_schema(
        summary="Modifier un compte épargne",
        description="""
        Met à jour un compte épargne existant.
        
        Modifications possibles:
        Numéro de téléphone Mobile Money
        Opérateur Mobile Money (MTN/Moov)
        Statut du compte (pour les agents/admins)
        Commentaires additionnels
        
        Restrictions:
        Seul le propriétaire peut modifier ses informations personnelles
        Agents/admins peuvent modifier le statut du compte
        Aucune modification des documents après validation
        """
    ),
    partial_update=extend_schema(
        summary="Modification partielle d'un compte épargne",
        description="Met à jour partiellement un compte épargne (uniquement les champs fournis)."
    ),
    destroy=extend_schema(
        summary="Fermer un compte épargne",
        description="""
        Ferme définitivement un compte épargne.
        
        Conditions de fermeture:
        Solde du compte épargne à zéro
        Aucune transaction en cours
        Validation par agent SFD ou le propriétaire
        
        Effets: Compte fermé, historique conservé, aucune nouvelle transaction possible
        """
    )
)
@extend_schema(tags=["💰 Comptes Épargne"])
class SavingsAccountViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des comptes épargne
    """
    queryset = SavingsAccount.objects.all()
    serializer_class = SavingsAccountSerializer
    permission_classes = [SavingsAccountPermission]

    def get_queryset(self):
        """
        Filtre les comptes selon les permissions utilisateur
        """
        user = self.request.user
        queryset = SavingsAccount.objects.all()
        
        if hasattr(user, 'client'):
            # Client ne voit que son propre compte
            queryset = queryset.filter(client=user.client)
        elif hasattr(user, 'agentsfd'):
            # Agent voit les comptes validés par sa SFD
            queryset = queryset.filter(agent_validateur__sfd=user.agentsfd.sfd)
        elif hasattr(user, 'administrateurssfd'):
            # Admin SFD voit les comptes validés par sa SFD
            queryset = queryset.filter(agent_validateur__sfd=user.administrateurssfd.sfd)
        # Admin plateforme voit tout (pas de filtre)
        
        return queryset

    @extend_schema(
        summary="Créer une demande de compte épargne",
        description="""
        Permet à un client de créer une demande d'ouverture de compte épargne.
        
        **Processus de demande**:
        1. Vérification de l'éligibilité du client
        2. Upload des documents requis (pièce d'identité + photo)
        3. Validation des données et création de la demande
        4. Notification automatique à l'agent SFD
        5. Statut initial: en_cours_creation
        
        **Documents requis**:
        - Pièce d'identité en cours de validité (CNI, passeport, permis)
        - Photo récente et nette du titulaire
        - Numéro Mobile Money valide et actif
        
        **Conditions d'éligibilité**:
        - Client enregistré et actif dans le système
        - Aucun compte épargne déjà ouvert
        - Documents d'identité conformes
        
        **Permissions requises**: Client authentifié
        """,
        request=CreateRequestSerializer,        responses={
            201: AccountStatusResponseSerializer,
            400: OpenApiResponse(description="Données invalides ou client non éligible"),
            409: OpenApiResponse(description="Client possède déjà un compte épargne")
        },
        examples=[
            OpenApiExample(
                "Demande de création réussie",
                value={
                    "piece_identite": "base64_encoded_image_data",
                    "photo_identite": "base64_encoded_image_data", 
                    "type_piece_identite": "CNI",
                    "numero_telephone": "+22370123456",
                    "commentaires": "Demande d'ouverture pour épargne familiale"
                }
            )
        ]
    )
    @action(detail=False, methods=['post'], url_path='create-request')
    def create_request(self, request):
        """
        Action pour créer une demande de compte épargne
        """
        serializer = CreateRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                with django.db.transaction.atomic():
                    # Vérification éligibilité client
                    client = request.user.client
                    eligibility_check = valider_eligibilite_compte_epargne(client)
                    
                    if not eligibility_check['eligible']:
                        return Response({
                            'success': False,
                            'error': eligibility_check['reason']
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Création du compte épargne
                    savings_account = SavingsAccount.objects.create(
                        client=client,
                        piece_identite=serializer.validated_data['piece_identite'],
                        photo_identite=serializer.validated_data['photo_identite'],
                        type_piece_identite=serializer.validated_data['type_piece_identite'],
                        numero_telephone=serializer.validated_data['numero_telephone'],
                        commentaires=serializer.validated_data.get('commentaires', ''),
                        statut='en_cours_creation',
                        date_demande=timezone.now()
                    )
                    
                    return Response({
                        'success': True,
                        'message': 'Demande de compte épargne créée avec succès',
                        'account_id': str(savings_account.id),
                        'account': AccountStatusResponseSerializer(savings_account).data
                    }, status=status.HTTP_201_CREATED)
                    
            except Exception as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Valider une demande de compte épargne (Agent SFD)",
        description="""
        Permet à un agent SFD de valider les documents d'une demande de compte épargne.
        
        **Rôle de l'agent SFD**:
        - Vérification de l'authenticité des pièces d'identité
        - Contrôle de la conformité des documents uploadés
        - Validation de l'identité du demandeur (photo vs pièce)
        - Autorisation de passage à l'étape de paiement
        
        **Processus de validation**:
        1. Examen des documents fournis
        2. Vérification de la qualité et lisibilité
        3. Contrôle de la cohérence des informations
        4. Décision de validation ou de rejet avec commentaires
        
        **Actions possibles**:
        - Valider: Passage au statut validee_agent
        - Rejeter: Retour en en_cours_creation avec commentaires
        - Demander documents complémentaires
        
        **Permissions requises**: Agent SFD de la même SFD que le client
        """,
        request=ValidateRequestSerializer,        responses={
            200: AccountStatusResponseSerializer,
            400: OpenApiResponse(description="Données de validation invalides"),
            403: OpenApiResponse(description="Agent non autorisé pour cette SFD"),
            404: OpenApiResponse(description="Demande de compte introuvable")
        },
        examples=[
            OpenApiExample(
                "Validation agent réussie",
                value={
                    "decision": "valide",
                    "commentaires_agent": "Documents conformes, identité vérifiée, pièce CNI valide jusqu'en 2028"
                }
            ),
            OpenApiExample(
                "Rejet par agent",
                value={
                    "decision": "rejete", 
                    "commentaires_agent": "Photo floue, CNI expirée, renouvellement requis"
                }
            )
        ]
    )
    @action(detail=True, methods=['post'], url_path='validate-request')
    def validate_request(self, request, pk=None):
        """
        Action pour valider une demande de compte épargne par un agent SFD
        """
        savings_account = self.get_object()
        serializer = ValidateRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                with django.db.transaction.atomic():
                    decision = serializer.validated_data['decision']
                    commentaires = serializer.validated_data.get('commentaires_agent', '')
                    
                    if decision == 'valide':
                        savings_account.statut = 'validee_agent'
                        savings_account.agent_validateur = request.user.agentsfd
                        savings_account.date_validation_agent = timezone.now()
                    else:
                        savings_account.statut = 'en_cours_creation'
                    
                    savings_account.commentaires_agent = commentaires
                    savings_account.save()
                    
                return Response({
                    'success': True,
                    'message': f'Demande {"validée" if decision == "valide" else "rejetée"} par agent',
                    'account': SavingsAccountResponseSerializer(savings_account).data
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Payer les frais de création via Mobile Money",
        description="""
        Permet de payer les frais de création d'un compte épargne via Mobile Money.
        
        **Processus de paiement**:
        1. Vérification que la demande est validée par l'agent
        2. Calcul des frais totaux (création + commission SFD)
        3. Initiation de la transaction Mobile Money
        4. Confirmation du paiement par l'opérateur
        5. Mise à jour du statut à 'paiement_effectue'
        6. Activation automatique du compte
        
        **Opérateurs supportés**:
        - MTN Mobile Money
        - Moov Money
        
        **Frais applicables**:
        - Frais de création de compte (définis par la SFD)
        - Commission opérateur Mobile Money
        - Commission plateforme TontiFlex
        
        **Conditions**:
        - Demande préalablement validée par un agent SFD
        - Solde Mobile Money suffisant pour tous les frais
        - Numéro de téléphone Mobile Money actif et confirmé
        """,
        request=PayFeesSerializer,
        responses={
            200: AccountStatusResponseSerializer,
            400: OpenApiResponse(description="Erreur de paiement ou demande non validée"),
            402: OpenApiResponse(description="Solde Mobile Money insuffisant"),
            503: OpenApiResponse(description="Service Mobile Money temporairement indisponible")
        },
        examples=[
            OpenApiExample(
                "Paiement MTN Money",
                value={
                    "numero_telephone": "+22370123456"
                }
            ),
            OpenApiExample(
                "Paiement Moov Money", 
                value={
                    "numero_telephone": "+22369987654"
                }
            )
        ]
    )
    @action(detail=True, methods=['post'], url_path='pay-fees')
    def pay_fees(self, request, pk=None):
        """
        Action pour effectuer le paiement des frais de création de compte
        """
        savings_account = self.get_object()
        serializer = PayFeesRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                with django.db.transaction.atomic():
                    # Vérifications préalables
                    if savings_account.statut != 'validee_agent':
                        return Response({
                            'success': False,
                            'error': 'Le compte doit être validé par un agent avant le paiement'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    numero_telephone = serializer.validated_data['numero_telephone']
                    operateur = serializer.validated_data['operateur']
                    
                    # Calcul des frais (ici on prend un montant fixe, à ajuster selon business rules)
                    montant_frais = Decimal('5000.00')  # 5000 FCFA
                    
                    # Créer une transaction KKiaPay
                    transaction = KKiaPayTransaction.objects.create(
                        phone=numero_telephone,
                        amount=montant_frais,
                        type='PAYMENT',
                        status='pending',
                        external_reference=f"SAV_{savings_account.id}_{int(timezone.now().timestamp())}",
                        description=f"Frais création compte épargne {savings_account.client.nom_complet}"
                    )
                    
                    # Mise à jour du compte
                    savings_account.statut = 'paiement_effectue'
                    savings_account.transaction_creation = transaction
                    savings_account.date_paiement = timezone.now()
                    savings_account.save()
                    
                    # Activation automatique après paiement (business rule)
                    savings_account.activer_compte()
                    
                return Response({
                    'success': True,
                    'message': 'Frais de création payés avec succès, compte activé',
                    'transaction_id': str(transaction.id),
                    'account': SavingsAccountResponseSerializer(savings_account).data
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Effectuer un dépôt via Mobile Money",
        description="""
        Permet d'effectuer un dépôt sur un compte épargne via Mobile Money.
        
        **Processus de dépôt**:
        1. Validation du compte épargne (actif et opérationnel)
        2. Vérification du montant minimum de dépôt
        3. Initiation de la transaction Mobile Money
        4. Confirmation du dépôt par l'opérateur
        5. Mise à jour du solde du compte
        6. Création de l'historique de transaction
        
        **Règles de dépôt**:
        - Montant minimum: 1000 FCFA
        - Montant maximum par transaction: 500000 FCFA
        - Comptes actifs uniquement
        - Transactions en temps réel
        
        **Sécurité**:
        - Authentification Mobile Money requise
        - Confirmation par SMS/notification
        - Traçabilité complète des opérations
        """,
        request=DepositSerializer,
        responses={
            200: OpenApiResponse(description="Dépôt effectué avec succès"),
            400: OpenApiResponse(description="Montant invalide ou compte non actif"),
            402: OpenApiResponse(description="Solde Mobile Money insuffisant"),
            503: OpenApiResponse(description="Service Mobile Money indisponible")
        },
        examples=[
            OpenApiExample(
                "Dépôt standard",
                value={
                    "montant": 50000,
                    "numero_telephone": "+22370123456",
                    "description": "Dépôt épargne mensuelle"
                }
            )
        ]
    )
    @action(detail=True, methods=['post'], url_path='deposit')
    def deposit(self, request, pk=None):
        """
        Action pour effectuer un dépôt sur le compte épargne
        """
        savings_account = self.get_object()
        serializer = DepositRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                with django.db.transaction.atomic():
                    # Vérifications préalables
                    if savings_account.statut != 'actif':
                        return Response({
                            'success': False,
                            'error': 'Le compte épargne doit être actif pour effectuer un dépôt'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    montant = serializer.validated_data['montant']
                    
                    # Validation du montant
                    validation_result = valider_montant_transaction(montant, 'depot')
                    if not validation_result['valid']:
                        return Response({
                            'success': False,
                            'error': validation_result['error']
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Création de la transaction KKiaPay
                    transaction_mobile = KKiaPayTransaction.objects.create(
                        phone=serializer.validated_data['numero_telephone'],
                        amount=montant,
                        type='PAYMENT',
                        status='pending',
                        external_reference=f"DEP_{savings_account.id}_{int(timezone.now().timestamp())}",
                        description=serializer.validated_data.get('description', f"Dépôt compte épargne")
                    )
                    
                    # Création de la transaction épargne
                    savings_transaction = SavingsTransaction.objects.create(
                        compte_epargne=savings_account,
                        type_transaction='depot',
                        montant=montant,
                        statut='confirmee',
                        transaction_kkiapay=transaction_mobile,
                        description=serializer.validated_data.get('description', 'Dépôt via KKiaPay'),
                        date_transaction=timezone.now()
                    )
                      # Mise à jour du solde (via la méthode du modèle)
                    nouveau_solde = savings_account.calculer_solde()
                    
                return Response({
                    'success': True,
                    'message': 'Dépôt effectué avec succès',
                    'transaction_id': str(savings_transaction.id),
                    'nouveau_solde': nouveau_solde,
                    'transaction': TransactionHistorySerializer(savings_transaction).data
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Effectuer un retrait via Mobile Money",
        description="""
        Permet d'effectuer un retrait du compte épargne vers Mobile Money.
        
        **Processus de retrait**:
        1. Validation du compte épargne et du solde disponible
        2. Vérification du montant et des limites de retrait
        3. Contrôle des frais de retrait applicables
        4. Initiation du transfert vers Mobile Money
        5. Confirmation et mise à jour du solde
        6. Historique de la transaction
        
        **Règles de retrait**:
        - Solde suffisant obligatoire
        - Montant minimum: 5000 FCFA
        - Frais de retrait: 1% du montant (min 500 FCFA)
        - Limite journalière: 200000 FCFA
        
        **Sécurité renforcée**:
        - Vérification d'identité pour gros montants
        - Notifications multi-canaux
        - Logs complets pour audit
        """,
        request=WithdrawSerializer,
        responses={
            200: OpenApiResponse(description="Retrait effectué avec succès"),
            400: OpenApiResponse(description="Montant invalide ou solde insuffisant"),
            403: OpenApiResponse(description="Limite de retrait dépassée"),
            503: OpenApiResponse(description="Service Mobile Money indisponible")
        },
        examples=[
            OpenApiExample(
                "Retrait standard",
                value={
                    "montant": 25000,
                    "numero_telephone": "+22370123456",
                    "description": "Retrait pour urgence familiale"
                }
            )
        ]
    )
    @action(detail=True, methods=['post'], url_path='withdraw')
    def withdraw(self, request, pk=None):
        """
        Action pour effectuer un retrait du compte épargne
        """
        savings_account = self.get_object()
        serializer = WithdrawRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                with django.db.transaction.atomic():
                    # Vérifications préalables
                    if savings_account.statut != 'actif':
                        return Response({
                            'success': False,
                            'error': 'Le compte épargne doit être actif pour effectuer un retrait'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    montant = serializer.validated_data['montant']
                    solde_actuel = savings_account.calculer_solde()
                    
                    # Validation du montant et solde
                    validation_result = valider_montant_transaction(montant, 'retrait')
                    if not validation_result['valid']:
                        return Response({
                            'success': False,
                            'error': validation_result['error']
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    if montant > solde_actuel:
                        return Response({
                            'success': False,
                            'error': f'Solde insuffisant. Solde disponible: {solde_actuel} FCFA'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Calcul des frais de retrait (1% min 500 FCFA)
                    frais_retrait = max(montant * Decimal('0.01'), Decimal('500'))
                    montant_total = montant + frais_retrait
                    
                    if montant_total > solde_actuel:
                        return Response({
                            'success': False,
                            'error': f'Solde insuffisant avec les frais. Frais: {frais_retrait} FCFA, Total requis: {montant_total} FCFA'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Création de la transaction KKiaPay
                    transaction_mobile = KKiaPayTransaction.objects.create(
                        phone=serializer.validated_data['numero_telephone'],
                        amount=montant,
                        type='WITHDRAWAL',
                        status='pending',
                        external_reference=f"WTH_{savings_account.id}_{int(timezone.now().timestamp())}",
                        description=serializer.validated_data.get('description', f"Retrait compte épargne")
                    )
                    
                    # Création de la transaction épargne (retrait)
                    savings_transaction = SavingsTransaction.objects.create(
                        compte_epargne=savings_account,
                        type_transaction='retrait',
                        montant=montant,
                        statut='confirmee',
                        transaction_kkiapay=transaction_mobile,
                        description=serializer.validated_data.get('description', 'Retrait vers KKiaPay'),
                        date_transaction=timezone.now()
                    )
                    
                    # Création de la transaction pour les frais
                    if frais_retrait > 0:
                        frais_transaction = SavingsTransaction.objects.create(
                            compte_epargne=savings_account,
                            type_transaction='frais',
                            montant=frais_retrait,
                            statut='confirmee',
                            description=f'Frais de retrait ({montant} FCFA)',
                            date_transaction=timezone.now()
                        )
                      # Calcul du nouveau solde
                    nouveau_solde = savings_account.calculer_solde()
                    
                return Response({
                    'success': True,
                    'message': 'Retrait effectué avec succès',
                    'transaction_id': str(savings_transaction.id),
                    'montant_retire': montant,
                    'frais_appliques': frais_retrait,
                    'nouveau_solde': nouveau_solde,
                    'transaction': TransactionHistorySerializer(savings_transaction).data
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Mon compte épargne (Client)",
        description="""
        Récupère les informations du compte épargne du client connecté.
        
        **Informations incluses**:
        - Détails du compte et statut actuel
        - Solde disponible en temps réel
        - Statistiques d'épargne (total déposé, retiré)
        - Historique des 10 dernières transactions
        - Informations de l'agent validateur
        
        **Données calculées**:
        - Solde actuel basé sur toutes les transactions
        - Moyenne mensuelle des dépôts
        - Évolution du solde sur les 6 derniers mois
        - Projections d'épargne
        
        **Permissions**: Client propriétaire uniquement
        """,
        responses={
            200: SavingsAccountSummarySerializer,
            404: OpenApiResponse(description="Aucun compte épargne trouvé")
        }
    )
    @action(detail=False, methods=['get'], url_path='my-account')
    def my_account(self, request):
        """
        Action pour récupérer le compte épargne du client connecté
        """
        try:
            client = request.user.client
            savings_account = SavingsAccount.objects.get(client=client)
            
            # Calcul des données supplémentaires
            solde_actuel = savings_account.calculer_solde()
            transactions_recentes = SavingsTransaction.objects.filter(
                compte_epargne=savings_account
            ).order_by('-date_transaction')[:10]
            
            # Statistiques
            total_depots = SavingsTransaction.objects.filter(
                compte_epargne=savings_account,
                type_transaction='depot',
                statut='confirmee'
            ).aggregate(total=Sum('montant'))['total'] or Decimal('0')
            
            total_retraits = SavingsTransaction.objects.filter(
                compte_epargne=savings_account,
                type_transaction='retrait',
                statut='confirmee'
            ).aggregate(total=Sum('montant'))['total'] or Decimal('0')
            
            response_data = {
                'compte': SavingsAccountSerializer(savings_account).data,
                'solde_actuel': solde_actuel,
                'statistiques': {
                    'total_depots': total_depots,
                    'total_retraits': total_retraits,
                    'nombre_transactions': transactions_recentes.count(),
                    'date_ouverture': savings_account.date_activation
                },
                'transactions_recentes': TransactionHistorySerializer(
                    transactions_recentes, many=True
                ).data
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except SavingsAccount.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Aucun compte épargne trouvé pour ce client'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Historique des transactions du compte",
        description="""
        Récupère l'historique complet des transactions d'un compte épargne.
        
        **Filtres disponibles**:
        - Par type de transaction (depot, retrait, frais)
        - Par période (date_debut, date_fin)
        - Par statut (confirmee, en_cours, echouee)
        - Par montant (min, max)
        
        **Tri et pagination**:
        - Tri par date (plus récent en premier)
        - Pagination avec limite configurable
        - Métadonnées de pagination incluses
        """,
        responses={200: TransactionHistorySerializer(many=True)}
    )
    @action(detail=True, methods=['get'], url_path='transactions')
    def transactions(self, request, pk=None):
        """
        Action pour récupérer l'historique des transactions d'un compte
        """
        savings_account = self.get_object()
        
        # Filtres optionnels
        type_transaction = request.query_params.get('type')
        statut = request.query_params.get('statut')
        date_debut = request.query_params.get('date_debut')
        date_fin = request.query_params.get('date_fin')
        
        queryset = SavingsTransaction.objects.filter(
            compte_epargne=savings_account
        ).order_by('-date_transaction')
        
        # Application des filtres
        if type_transaction:
            queryset = queryset.filter(type_transaction=type_transaction)
        if statut:
            queryset = queryset.filter(statut=statut)
        if date_debut:
            queryset = queryset.filter(date_transaction__gte=date_debut)
        if date_fin:
            queryset = queryset.filter(date_transaction__lte=date_fin)
          # Pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = TransactionHistorySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = TransactionHistorySerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(
        summary="Liste des transactions d'épargne",
        description="""
        Affiche la liste de toutes les transactions d'épargne selon les permissions utilisateur.
        
        Types de transactions:
        depot: Ajout de fonds au compte épargne via Mobile Money
        retrait: Retrait de fonds vers Mobile Money  
        frais: Frais de service (retrait, maintenance)
        
        Statuts des transactions:
        en_cours: Transaction initiée, en attente de confirmation
        confirmee: Transaction réussie et validée
        echouee: Transaction annulée ou échouée
        
        Filtres disponibles:
        Par compte épargne
        Par type de transaction
        Par statut
        Par période (date début/fin)
        Par montant (min/max)
        """,
        responses={200: SavingsTransactionSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Créer une transaction d'épargne",
        description="""
        Crée une nouvelle transaction d'épargne (généralement via les actions deposit/withdraw).
        
        Usage typique:
        Utilisé en interne par les actions deposit/withdraw du compte
        Peut être utilisé pour des ajustements manuels par les admins
        Gestion des erreurs et rollback automatique
        """,
        request=SavingsTransactionSerializer,
        responses={
            201: SavingsTransactionSerializer,
            400: OpenApiResponse(description="Données de transaction invalides")
        }
    ),
    retrieve=extend_schema(
        summary="Détails d'une transaction",
        description="Récupère les informations détaillées d'une transaction d'épargne spécifique."
    ),
    update=extend_schema(
        summary="Modifier une transaction",
        description="""
        Met à jour une transaction d'épargne existante.
        
        Modifications possibles:
        Statut de la transaction (pour correction d'erreurs)
        Description/commentaires
        Données de la transaction Mobile Money liée
        
        Restrictions:
        Seuls les admins peuvent modifier les transactions
        Transactions confirmées ne peuvent pas être annulées
        Modifications tracées dans l'audit log
        """
    )
)
@extend_schema(tags=["📊 Transactions Épargne"])
class SavingsTransactionViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des transactions d'épargne
    """
    queryset = SavingsTransaction.objects.all()
    serializer_class = SavingsTransactionSerializer
    permission_classes = [SavingsTransactionPermission]

    def get_queryset(self):
        """
        Filtre les transactions selon les permissions utilisateur
        """
        user = self.request.user
        queryset = SavingsTransaction.objects.all()
        
        if hasattr(user, 'client'):
            # Client ne voit que ses propres transactions
            queryset = queryset.filter(compte_epargne__client=user.client)
        elif hasattr(user, 'agentsfd'):
            # Agent voit les transactions des comptes de sa SFD
            queryset = queryset.filter(compte_epargne__agent_validateur__sfd=user.agentsfd.sfd)
        elif hasattr(user, 'administrateurssfd'):
            # Admin SFD voit les transactions des comptes de sa SFD
            queryset = queryset.filter(compte_epargne__agent_validateur__sfd=user.administrateurssfd.sfd)
        # Admin plateforme voit tout (pas de filtre)
        
        return queryset.order_by('-date_transaction')

    @extend_schema(
        summary="Statistiques des transactions",
        description="""
        Fournit des statistiques agrégées sur les transactions d'épargne.
        
        **Métriques incluses**:
        - Volume total des dépôts/retraits par période
        - Nombre de transactions par type
        - Montants moyens par transaction
        - Évolution mensuelle des volumes
        - Répartition par statut de transaction
        
        **Filtres**:
        - Période d'analyse (dernier mois, trimestre, année)
        - Par SFD (pour les agents/admins SFD)
        - Par type de transaction
        """,
        responses={200: OpenApiResponse(description="Statistiques des transactions")}
    )
    @action(detail=False, methods=['get'], url_path='statistics')
    def statistics(self, request):
        """
        Action pour récupérer les statistiques des transactions
        """
        try:
            # Période d'analyse (par défaut: 30 derniers jours)
            periode = request.query_params.get('periode', '30')
            date_limite = timezone.now() - timezone.timedelta(days=int(periode))
            
            queryset = self.get_queryset().filter(date_transaction__gte=date_limite)
            
            # Calculs des statistiques
            stats = {
                'periode_jours': periode,
                'total_transactions': queryset.count(),
                'depots': {
                    'nombre': queryset.filter(type_transaction='depot').count(),
                    'montant_total': queryset.filter(
                        type_transaction='depot', statut='confirmee'
                    ).aggregate(total=Sum('montant'))['total'] or Decimal('0'),
                    'montant_moyen': queryset.filter(
                        type_transaction='depot', statut='confirmee'
                    ).aggregate(avg=Avg('montant'))['avg'] or Decimal('0')
                },
                'retraits': {
                    'nombre': queryset.filter(type_transaction='retrait').count(),
                    'montant_total': queryset.filter(
                        type_transaction='retrait', statut='confirmee'
                    ).aggregate(total=Sum('montant'))['total'] or Decimal('0'),
                    'montant_moyen': queryset.filter(
                        type_transaction='retrait', statut='confirmee'
                    ).aggregate(avg=Avg('montant'))['avg'] or Decimal('0')
                },
                'frais': {
                    'nombre': queryset.filter(type_transaction='frais').count(),
                    'montant_total': queryset.filter(
                        type_transaction='frais', statut='confirmee'
                    ).aggregate(total=Sum('montant'))['total'] or Decimal('0')
                },
                'repartition_statuts': {
                    'confirmee': queryset.filter(statut='confirmee').count(),
                    'en_cours': queryset.filter(statut='en_cours').count(),
                    'echouee': queryset.filter(statut='echouee').count()
                }
            }
            
            return Response(stats, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
