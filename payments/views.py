from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from .services import kkiapay_service
# --- Endpoint API pour valider un token et retourner la transaction (pour le widget JS) ---
class TransactionFromTokenView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        token = request.GET.get('token')
        if not token:
            return Response({'error': 'Token manquant'}, status=400)
        try:
            transaction_id = kkiapay_service.validate_payment_token(token)
            tx = KKiaPayTransaction.objects.get(id=transaction_id)
            data = {
                'id': str(tx.id),
                'montant': float(tx.montant),
                'type_transaction': tx.type_transaction,
                'description': tx.description,
                'public_key': kkiapay_config.public_key,
                'callback_url': tx.callback_url or kkiapay_config.webhook_url,
                'numero_telephone': tx.numero_telephone,
            }
            return Response(data)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

# --- Vue Django pour servir le template widget.html ---
from django.views import View
class PaymentWidgetView(View):
    def get(self, request):
        return render(request, 'payments/widget.html')
"""
Views Django REST Framework pour le module Payments KKiaPay
===========================================================

API endpoints unifiés pour toutes les transactions financières via KKiaPay.
Compatible avec la documentation officielle KKiaPay Sandbox.
"""
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample
from django.utils import timezone
from decimal import Decimal
import logging

from .models import KKiaPayTransaction
from .serializers import (
    KKiaPayTransactionSerializer, 
    PaymentInitiationSerializer,
    PaymentStatusSerializer,
    SandboxTestSerializer
)
from .services import kkiapay_service, KKiaPayException
from .config import kkiapay_config
from .webhooks import KKiaPayWebhookView

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="Liste des transactions KKiaPay",
        description="""
        Affiche l'historique des transactions KKiaPay de la plateforme TontiFlex.
        
        **Mode SANDBOX actif** - Utilise l'environnement de test KKiaPay
        
        Types de transactions supportés:
        - **Tontines**: Adhésion, cotisations, retraits
        - **Épargne**: Création compte, dépôts, retraits  
        - **Prêts**: Remboursements
        
        Statuts disponibles:
        - `pending`: En attente de paiement
        - `processing`: En cours de traitement chez KKiaPay
        - `success`: Paiement confirmé
        - `failed`: Paiement échoué
        - `cancelled`: Paiement annulé
        - `refunded`: Paiement remboursé
        
        **Documentation**: https://docs.kkiapay.me/v1/compte/kkiapay-sandbox-guide-de-test
        """,
        responses={200: KKiaPayTransactionSerializer(many=True)}
    ),
    retrieve=extend_schema(
        summary="Détails d'une transaction KKiaPay",
        description="Récupère les détails complets d'une transaction KKiaPay incluant les réponses API.",
        responses={200: KKiaPayTransactionSerializer}
    )
)
@extend_schema(tags=["💳 Paiements KKiaPay"])
class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour la gestion des transactions KKiaPay
    """
    queryset = KKiaPayTransaction.objects.all()
    serializer_class = KKiaPayTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filtre les transactions selon les permissions utilisateur"""
        user = self.request.user
        
        # Admin plateforme voit tout
        if hasattr(user, 'adminplateforme'):
            return KKiaPayTransaction.objects.all()
        
        # Les autres voient leurs propres transactions
        return KKiaPayTransaction.objects.filter(user=user)
    
    @extend_schema(
        summary="Initier un paiement KKiaPay",
        description="""
        Initie un nouveau paiement via KKiaPay en mode SANDBOX.
        
        **Numéros de test SANDBOX** (selon documentation officielle):
        
        **📱 MTN Bénin - Succès:**
        - `+22997000001` - Succès immédiat
        - `+22997000002` - Succès avec délai 1-2 min
        
        **📱 MTN Côte d'Ivoire - Succès:**
        - `+22507000001` - Succès immédiat
        - `+22507000002` - Succès avec délai
        
        **📱 MOOV - Succès:**
        - `+22996000001` - Succès immédiat
        - `+22996000002` - Succès avec délai
        
        **⚠️ Numéros d'échec:**
        - `+22997000999` - Simulation d'échec
        - `+22996000999` - Simulation d'échec
        
        Le système vérifiera automatiquement le statut et déclenchera les webhooks.
        """,
        request=PaymentInitiationSerializer,
        responses={
            201: KKiaPayTransactionSerializer,
            400: "Erreur de validation ou configuration",
            500: "Erreur technique KKiaPay"
        },
        examples=[
            OpenApiExample(
                "Paiement adhésion tontine",
                value={
                    "montant": "5000.00",
                    "numero_telephone": "+22997000001",
                    "type_transaction": "adhesion_tontine",
                    "description": "Frais d'adhésion Tontine Solidaire",
                    "objet_id": 123,
                    "objet_type": "Tontine"
                }
            ),
            OpenApiExample(
                "Cotisation tontine",
                value={
                    "montant": "10000.00",
                    "numero_telephone": "+22996000001",
                    "type_transaction": "cotisation_tontine",
                    "description": "Cotisation mensuelle",
                    "objet_id": 123,
                    "objet_type": "Tontine"
                }
            )
        ]
    )
    @action(detail=False, methods=['post'], url_path='initiate')
    def initiate_payment(self, request):
        """
        Initie un nouveau paiement KKiaPay
        """
        serializer = PaymentInitiationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Vérification de la configuration
            if not kkiapay_config.is_configured():
                return Response(
                    {"error": "Configuration KKiaPay incomplète"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Initiation du paiement via le service
            transaction = kkiapay_service.initiate_payment(
                user=request.user,
                amount=serializer.validated_data['montant'],
                phone_number=serializer.validated_data['numero_telephone'],
                transaction_type=serializer.validated_data['type_transaction'],
                description=serializer.validated_data.get('description', ''),
                object_id=serializer.validated_data.get('objet_id'),
                object_type=serializer.validated_data.get('objet_type', '')
            )
            
            # Sérialisation de la réponse
            response_serializer = KKiaPayTransactionSerializer(transaction)
            
            logger.info(f"✅ Paiement initié: {transaction.reference_tontiflex}")
            
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except KKiaPayException as e:
            logger.error(f"❌ Erreur KKiaPay: {str(e)}")
            return Response(
                {"error": str(e), "error_code": e.error_code},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"❌ Erreur système: {str(e)}")
            return Response(
                {"error": "Erreur technique lors de l'initiation du paiement"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Vérifier le statut d'une transaction",
        description="""
        Vérifie le statut actuel d'une transaction auprès de KKiaPay.
        
        Utilise l'API KKiaPay pour obtenir le statut en temps réel.
        Met à jour automatiquement la base de données locale.
        """,
        request=PaymentStatusSerializer,
        responses={
            200: KKiaPayTransactionSerializer,
            404: "Transaction introuvable",
            400: "Erreur de validation"
        }
    )
    @action(detail=False, methods=['post'], url_path='check-status')
    def check_status(self, request):
        """
        Vérifie le statut d'une transaction KKiaPay
        """
        serializer = PaymentStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Recherche de la transaction
            transaction = KKiaPayTransaction.objects.get(
                reference_tontiflex=serializer.validated_data['reference_tontiflex'],
                user=request.user
            )
            
            # Vérification du statut auprès de KKiaPay
            status_updated = kkiapay_service.check_transaction_status(transaction)
            
            # Réponse avec le statut mis à jour
            response_serializer = KKiaPayTransactionSerializer(transaction)
            
            return Response({
                "transaction": response_serializer.data,
                "status_updated": status_updated,
                "message": "Statut vérifié avec succès"
            })
            
        except KKiaPayTransaction.DoesNotExist:
            return Response(
                {"error": "Transaction introuvable"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"❌ Erreur vérification statut: {str(e)}")
            return Response(
                {"error": "Erreur lors de la vérification du statut"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Tests SANDBOX KKiaPay",
        description="""
        **🧪 SANDBOX UNIQUEMENT** - Endpoints de test selon la documentation KKiaPay.
        
        Permet de tester les différents scénarios:
        - **Succès**: Transaction réussie immédiatement
        - **Échec**: Simulation d'erreur de paiement  
        - **Timeout**: Simulation de timeout (1-2 min)
        
        Utilise automatiquement les bons numéros de test selon le scénario choisi.
        
        **⚠️ Disponible uniquement en mode SANDBOX**
        """,
        request=SandboxTestSerializer,
        responses={
            200: KKiaPayTransactionSerializer,
            403: "Mode SANDBOX requis",
            400: "Erreur de test"
        }
    )
    @action(detail=False, methods=['post'], url_path='sandbox-test')
    def sandbox_test(self, request):
        """
        Tests en mode SANDBOX selon la documentation KKiaPay
        """
        if not kkiapay_config.sandbox:
            return Response(
                {"error": "Tests disponibles uniquement en mode SANDBOX"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = SandboxTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Numéros de test selon la documentation officielle
        test_numbers = {
            'success': '+22997000001',  # MTN Bénin - Succès immédiat
            'failure': '+22997000999',  # Numéro d'échec
            'timeout': '+22997000002',  # Succès avec délai 1-2 min
        }
        
        scenario = serializer.validated_data['scenario']
        phone_number = test_numbers[scenario]
        
        try:
            # Initiation du paiement de test
            transaction = kkiapay_service.initiate_payment(
                user=request.user,
                amount=serializer.validated_data['montant'],
                phone_number=phone_number,
                transaction_type='autre',
                description=f"Test SANDBOX - Scénario: {scenario}",
                object_id=None,
                object_type='SandboxTest'
            )
            
            response_serializer = KKiaPayTransactionSerializer(transaction)
            
            return Response({
                "transaction": response_serializer.data,
                "test_scenario": scenario,
                "test_phone": phone_number,
                "message": f"Test {scenario} initié avec succès",
                "documentation": "https://docs.kkiapay.me/v1/compte/kkiapay-sandbox-guide-de-test"
            })
            
        except Exception as e:
            logger.error(f"❌ Erreur test SANDBOX: {str(e)}")
            return Response(
                {"error": f"Erreur lors du test: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


# --- Endpoint API pour générer un lien de paiement sécurisé ---
from rest_framework import serializers

class GeneratePaymentLinkSerializer(serializers.Serializer):
    montant = serializers.DecimalField(max_digits=15, decimal_places=2)
    numero_telephone = serializers.CharField(max_length=20)
    type_transaction = serializers.CharField(max_length=50)
    description = serializers.CharField(max_length=200, required=False)
    objet_id = serializers.IntegerField(required=False)
    objet_type = serializers.CharField(max_length=50, required=False)
    metadata = serializers.JSONField(required=False)
    callback_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import kkiapay_service

class GeneratePaymentLinkView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = GeneratePaymentLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        data = serializer.validated_data
        # Création de la transaction en base
        transaction = kkiapay_service.initiate_payment(
            user=user,
            amount=data["montant"],
            phone_number=data["numero_telephone"],
            transaction_type=data["type_transaction"],
            description=data.get("description", ""),
            object_id=data.get("objet_id"),
            object_type=data.get("objet_type", ""),
        )
        # Génération du lien sécurisé
        payment_link = kkiapay_service.generate_payment_link(transaction.id, return_url=data.get("callback_url"))
        return Response({"payment_link": payment_link, "transaction_id": str(transaction.id)}, status=201)

# Vue pour les webhooks (incluse dans ce module)
webhook_view = KKiaPayWebhookView.as_view()
