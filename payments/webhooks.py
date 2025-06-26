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
import json

from .services import kkiapay_service
from .config import kkiapay_config

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(require_POST, name='dispatch')
class KKiaPayWebhookView(View):
    """
    Vue pour traiter les webhooks KKiaPay
    """
    
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
                return HttpResponseBadRequest("Signature invalide")
            
            # Parsing des données JSON
            webhook_data = json.loads(payload.decode('utf-8'))
            
            logger.info(f"📥 Webhook KKiaPay reçu: {webhook_data.get('type', 'UNKNOWN')}")
            
            # Traitement du webhook via le service
            transaction = kkiapay_service.process_webhook(webhook_data)
            
            if transaction:
                logger.info(f"✅ Webhook traité avec succès: {transaction.reference_tontiflex}")
                
                # Déclencher les actions post-paiement selon le type
                self._trigger_post_payment_actions(transaction)
                
                return HttpResponse("Webhook traité avec succès", status=200)
            else:
                logger.error("❌ Échec du traitement du webhook")
                return HttpResponseBadRequest("Échec du traitement")
                
        except json.JSONDecodeError:
            logger.error("❌ Payload webhook invalide (JSON malformé)")
            return HttpResponseBadRequest("JSON invalide")
        except Exception as e:
            logger.error(f"❌ Erreur traitement webhook: {str(e)}")
            return HttpResponseBadRequest(f"Erreur: {str(e)}")
    
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
        
    def _handle_tontine_cotisation_success(self, transaction):
        """Actions après réussite d'une cotisation tontine"""
        logger.info(f"💰 Traitement cotisation tontine réussie: {transaction.reference_tontiflex}")
        # TODO: Intégrer avec le modèle Cotisation
        
    def _handle_savings_success(self, transaction):
        """Actions après réussite d'une transaction épargne"""
        logger.info(f"🏦 Traitement épargne réussie: {transaction.reference_tontiflex}")
        # TODO: Intégrer avec le modèle SavingsAccount
        
    def _handle_loan_repayment_success(self, transaction):
        """Actions après réussite d'un remboursement prêt"""
        logger.info(f"💳 Traitement remboursement prêt réussi: {transaction.reference_tontiflex}")
        # TODO: Intégrer avec le modèle Loan


def webhook_view(request):
    """
    Vue fonction pour les webhooks KKiaPay (alternative)
    """
    return KKiaPayWebhookView.as_view()(request)
