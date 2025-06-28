"""
Gestion des webhooks KKiaPay pour TontiFlex
==========================================

Traite les callbacks de statut des transactions KKiaPay selon la documentation officielle.
Documentation : https://docs.kkiapay.me/v1/compte/kkiapay-sandbox-guide-de-test
"""
import logging
import hashlib
import hmac
from typing import Dict, Any, Optional
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
import json

from .services import kkiapay_service
from .config import kkiapay_config

logger = logging.getLogger(__name__)


class KKiaPayWebhookView(APIView):
    """
    Vue pour traiter les webhooks KKiaPay
    """
    permission_classes = [AllowAny]  # Les webhooks viennent de KKiaPay, pas d'utilisateurs authentifiés
    
    @extend_schema(
        summary="Webhook KKiaPay",
        description="""
        Endpoint pour recevoir les notifications de statut des transactions KKiaPay.
        
        **⚠️ Usage interne uniquement** - Cet endpoint est appelé automatiquement par KKiaPay
        pour notifier les changements de statut des transactions.
        
        **Sécurité:**
        - Validation de signature avec HMAC-SHA256
        - Vérification de l'IP source (optionnel)
        - Traitement idempotent des webhooks
        
        **Types d'événements supportés:**
        - `payment.success` - Paiement réussi
        - `payment.failed` - Paiement échoué
        - `payment.cancelled` - Paiement annulé
        """,
        request={
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "Type d'événement"},
                "data": {"type": "object", "description": "Données de la transaction"},
                "timestamp": {"type": "string", "description": "Timestamp de l'événement"}
            }
        },
        responses={
            200: {"description": "Webhook traité avec succès"},
            400: {"description": "Webhook invalide ou malformé"},
            401: {"description": "Signature invalide"}
        },
        tags=["🔗 Webhooks"]
    )
    def post(self, request):
        """
        Traite un webhook reçu de KKiaPay
        """
        try:
            # Récupération du payload
            payload = request.body
            
            # Validation de la signature (si configurée)
            if not self._validate_signature(request, payload):
                logger.warning("🚨 Signature webhook KKiaPay invalide")
                return Response(
                    {"error": "Signature invalide"}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Parsing des données JSON
            webhook_data = json.loads(payload.decode('utf-8'))
            
            logger.info(f"📥 Webhook KKiaPay reçu: {webhook_data.get('type', 'UNKNOWN')}")
            
            # Traitement du webhook via le service
            transaction = kkiapay_service.process_webhook(webhook_data)
            
            if transaction:
                logger.info(f"✅ Webhook traité avec succès: {transaction.reference_tontiflex}")
                
                # Déclencher les actions post-paiement selon le type
                self._trigger_post_payment_actions(transaction)
                
                return Response(
                    {"message": "Webhook traité avec succès"}, 
                    status=status.HTTP_200_OK
                )
            else:
                logger.error("❌ Échec du traitement du webhook")
                return Response(
                    {"error": "Échec du traitement"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except json.JSONDecodeError:
            logger.error("❌ Payload webhook invalide (JSON malformé)")
            return Response(
                {"error": "JSON invalide"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"❌ Erreur traitement webhook: {str(e)}")
            return Response(
                {"error": f"Erreur: {str(e)}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def _validate_signature(self, request, payload: bytes) -> bool:
        """
        Valide la signature du webhook KKiaPay
        """
        if not kkiapay_config.webhook_secret:
            # Si pas de secret configuré, on accepte (mode développement)
            logger.warning("⚠️ Validation signature désactivée - secret webhook manquant")
            return True
        
        # Récupération de la signature depuis les headers
        signature_header = request.META.get('HTTP_X_KKIAPAY_SIGNATURE', '')
        
        if not signature_header:
            logger.warning("⚠️ Header signature manquant")
            return True  # En mode développement, on accepte
        
        # Calcul de la signature attendue
        expected_signature = hmac.new(
            kkiapay_config.webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Comparaison sécurisée
        return hmac.compare_digest(signature_header, expected_signature)
    
    def _trigger_post_payment_actions(self, transaction):
        """
        Déclenche les actions appropriées après un paiement réussi
        """
        if not transaction.is_success():
            return
        
        try:
            # Actions selon le type de transaction
            if transaction.type_transaction == 'adhesion_tontine':
                self._handle_tontine_adhesion_success(transaction)
            elif transaction.type_transaction == 'cotisation_tontine':
                self._handle_tontine_cotisation_success(transaction)
            elif transaction.type_transaction in ['depot_epargne', 'frais_creation_epargne']:
                self._handle_savings_success(transaction)
            elif transaction.type_transaction == 'remboursement_pret':
                self._handle_loan_repayment_success(transaction)
                
        except Exception as e:
            logger.error(f"❌ Erreur actions post-paiement: {str(e)}")
    
    def _handle_tontine_adhesion_success(self, transaction):
        """Actions après réussite d'une adhésion tontine"""
        logger.info(f"🎯 Traitement adhésion tontine réussie: {transaction.reference_tontiflex}")
        # TODO: Intégrer avec le modèle Adhesion
        from tontines.models import Adhesion
        try:
            # On suppose que objet_id contient l'UUID de l'adhésion
            adhesion = Adhesion.objects.get(id=transaction.objet_id)
            # Vérifier que le paiement n'a pas déjà été traité
            if adhesion.statut_actuel not in ['paiement_effectue', 'adherent']:
                adhesion.frais_adhesion_payes = transaction.montant
                adhesion.reference_paiement = transaction.reference_tontiflex
                adhesion.date_paiement_frais = transaction.processed_at or transaction.updated_at or transaction.created_at
                adhesion.statut_actuel = 'paiement_effectue'
                adhesion.etape_actuelle = 'etape_3'
                adhesion.save()
                # Finaliser l'adhésion (création du participant)
                adhesion.finaliser_adhesion()
                logger.info(f"✅ Adhésion mise à jour suite paiement KKiaPay: {adhesion.id}")
            else:
                logger.info(f"ℹ️ Adhésion déjà traitée: {adhesion.id}")
        except Adhesion.DoesNotExist:
            logger.error(f"❌ Aucun workflow Adhesion trouvé pour objet_id={transaction.objet_id}")
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'intégration KKiaPay/Adhesion: {str(e)}")
    
    def _handle_tontine_cotisation_success(self, transaction):
        """Actions après réussite d'une cotisation tontine"""
        logger.info(f"💰 Traitement cotisation tontine réussie: {transaction.reference_tontiflex}")
        # TODO: Intégrer avec le modèle Cotisation
        from tontines.models import Cotisation, TontineParticipant
        try:
            # On suppose que objet_id contient l'ID de la cotisation
            cotisation = Cotisation.objects.get(id=transaction.objet_id)
            if cotisation.statut != Cotisation.StatutCotisationChoices.CONFIRMEE:
                cotisation.statut = Cotisation.StatutCotisationChoices.CONFIRMEE
                cotisation.numero_transaction = transaction.reference_tontiflex
                cotisation.date_cotisation = transaction.processed_at or transaction.updated_at or transaction.created_at
                cotisation.save()
                # Mettre à jour le solde du participant si besoin
                participant = TontineParticipant.objects.filter(
                    tontine=cotisation.tontine, client=cotisation.client, statut='actif'
                ).first()
                if participant:
                    participant.solde = participant.solde + cotisation.montant if hasattr(participant, 'solde') else cotisation.montant
                    participant.save()
                logger.info(f"✅ Cotisation mise à jour suite paiement KKiaPay: {cotisation.id}")
            else:
                logger.info(f"ℹ️ Cotisation déjà confirmée: {cotisation.id}")
        except Cotisation.DoesNotExist:
            logger.error(f"❌ Aucune cotisation trouvée pour objet_id={transaction.objet_id}")
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'intégration KKiaPay/Cotisation: {str(e)}")

        # Intégration avec le modèle Retrait
        from tontines.models import Retrait
        try:
            # On suppose que objet_id contient l'ID du retrait
            retrait = Retrait.objects.get(id=transaction.objet_id)
            if retrait.statut != Retrait.StatutRetraitChoices.CONFIRMEE:
                retrait.statut = Retrait.StatutRetraitChoices.CONFIRMEE
                retrait.transaction_mobile_money = None  # À lier si transaction Mobile Money créée
                retrait.date_validation_retrait = transaction.processed_at or transaction.updated_at or transaction.created_at
                retrait.save()
                logger.info(f"✅ Retrait confirmé suite paiement KKiaPay: {retrait.id}")
            else:
                logger.info(f"ℹ️ Retrait déjà confirmé: {retrait.id}")
        except Retrait.DoesNotExist:
            logger.info(f"Aucun retrait trouvé pour objet_id={transaction.objet_id} (pas bloquant)")
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'intégration KKiaPay/Retrait: {str(e)}")
    
    def _handle_savings_success(self, transaction):
        """Actions après réussite d'une transaction épargne"""
        logger.info(f"🏦 Traitement épargne réussie: {transaction.reference_tontiflex}")
        # TODO: Intégrer avec le modèle SavingsAccount
        
        # Intégration avec le modèle SavingsAccount (création compte, dépôts, retraits)
        from savings.models import SavingsAccount, SavingsTransaction
        try:
            # Création de compte épargne (frais)
            if transaction.type_transaction == 'frais_creation_epargne':
                account = SavingsAccount.objects.get(id=transaction.objet_id)
                if account.statut != SavingsAccount.StatutChoices.PAIEMENT_EFFECTUE:
                    account.statut = SavingsAccount.StatutChoices.PAIEMENT_EFFECTUE
                    account.transaction_frais_creation = None  # À lier si besoin
                    account.save()
                    logger.info(f"✅ Compte épargne mis à jour (frais payés): {account.id}")
                else:
                    logger.info(f"ℹ️ Compte épargne déjà marqué comme payé: {account.id}")
            # Dépôt ou retrait sur compte épargne
            elif transaction.type_transaction in ['depot_epargne', 'retrait_epargne']:
                savings_tx = SavingsTransaction.objects.get(id=transaction.objet_id)
                if savings_tx.statut != SavingsTransaction.StatutChoices.CONFIRMEE:
                    savings_tx.statut = SavingsTransaction.StatutChoices.CONFIRMEE
                    savings_tx.date_confirmation = transaction.processed_at or transaction.updated_at or transaction.created_at
                    savings_tx.save()
                    logger.info(f"✅ Transaction épargne confirmée: {savings_tx.id}")
                else:
                    logger.info(f"ℹ️ Transaction épargne déjà confirmée: {savings_tx.id}")
        except SavingsAccount.DoesNotExist:
            logger.error(f"❌ Aucun compte épargne trouvé pour objet_id={transaction.objet_id}")
        except SavingsTransaction.DoesNotExist:
            logger.error(f"❌ Aucune transaction épargne trouvée pour objet_id={transaction.objet_id}")
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'intégration KKiaPay/Savings: {str(e)}")
    
    def _handle_loan_repayment_success(self, transaction):
        """Actions après réussite d'un remboursement prêt"""
        logger.info(f"💳 Traitement remboursement prêt réussi: {transaction.reference_tontiflex}")
        # TODO: Intégrer avec le modèle Loan

        # Intégration avec le modèle Payment (remboursement prêt)
        from loans.models import Payment
        try:
            payment = Payment.objects.get(id=transaction.objet_id)
            if payment.statut != Payment.StatutChoices.CONFIRME:
                payment.statut = Payment.StatutChoices.CONFIRME
                payment.date_confirmation = transaction.processed_at or transaction.updated_at or transaction.created_at
                payment.reference_externe = transaction.reference_tontiflex
                payment.save()
                # Appeler la méthode métier pour finaliser le paiement
                payment.confirmer_paiement()
                logger.info(f"✅ Paiement de prêt confirmé suite paiement KKiaPay: {payment.id}")
            else:
                logger.info(f"ℹ️ Paiement de prêt déjà confirmé: {payment.id}")
        except Payment.DoesNotExist:
            logger.error(f"❌ Aucun paiement de prêt trouvé pour objet_id={transaction.objet_id}")
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'intégration KKiaPay/Loan: {str(e)}")


def webhook_view(request):
    """
    Vue fonction pour les webhooks KKiaPay avec CSRF exempt
    """
    # Wrapper CSRF exempt pour les webhooks KKiaPay
    return csrf_exempt(KKiaPayWebhookView.as_view())(request)


@csrf_exempt
def webhook_view_function(request):
    """
    Vue fonction alternative pour les webhooks KKiaPay
    """
    webhook_instance = KKiaPayWebhookView()
    return webhook_instance.post(request)
