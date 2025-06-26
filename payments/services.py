"""
Service KKiaPay centralisé pour TontiFlex
========================================

Service unifié pour toutes les transactions financières via KKiaPay.
Remplace les services MTN/Moov/Orange par une interface unique.

Documentation : https://kkiapay.me/kkiapay-integration/?lang=en
SDK Python : https://github.com/PythonBenin/kkiapay-python
"""
import logging
# import requests  # Importé à la demande pour éviter les conflits de version
from decimal import Decimal
from typing import Dict, Any, Optional
from django.utils import timezone
from django.conf import settings

from .config import kkiapay_config
from .models import KKiaPayTransaction

logger = logging.getLogger(__name__)


class KKiaPayException(Exception):
    """Exception personnalisée pour les erreurs KKiaPay"""
    def __init__(self, message: str, error_code: str = "", response_data: Dict = None):
        super().__init__(message)
        self.error_code = error_code
        self.response_data = response_data or {}


class KKiaPayService:
    """
    Service centralisé pour toutes les opérations KKiaPay
    """
    
    def __init__(self):
        """Initialise le service KKiaPay"""
        # Import à la demande pour éviter les conflits de version au démarrage
        try:
            import requests
            self.requests = requests
        except ImportError as e:
            logger.error(f"❌ Impossible d'importer requests: {e}")
            raise KKiaPayException("Module requests requis non disponible")
        
        self.config = kkiapay_config
        self.session = self.requests.Session()
        
        # Headers par défaut
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-PUBLIC-KEY': self.config.public_key,
            'X-SECRET-KEY': self.config.secret_key,
        })
        
        # Vérification de la configuration
        if not self.config.is_configured():
            logger.error("❌ Configuration KKiaPay incomplète")
            raise KKiaPayException("Configuration KKiaPay manquante")
        
        logger.info(f"✅ Service KKiaPay initialisé en mode {'SANDBOX' if self.config.sandbox else 'LIVE'}")
    
    def initiate_payment(self, 
                        user,
                        amount: Decimal,
                        phone_number: str,
                        transaction_type: str,
                        description: str = "",
                        object_id: Optional[int] = None,
                        object_type: str = "") -> KKiaPayTransaction:
        """
        Initie un paiement KKiaPay
        
        Args:
            user: Utilisateur Django
            amount: Montant à payer
            phone_number: Numéro de téléphone Mobile Money
            transaction_type: Type de transaction (adhesion_tontine, cotisation_tontine, etc.)
            description: Description optionnelle
            object_id: ID de l'objet concerné (tontine, compte épargne, etc.)
            object_type: Type d'objet concerné
            
        Returns:
            KKiaPayTransaction: Transaction créée
        """
        logger.info(f"🚀 Initiation paiement KKiaPay: {amount} XOF pour {user.username}")
        
        # Création de la transaction en base
        transaction = KKiaPayTransaction.objects.create(
            user=user,
            montant=amount,
            numero_telephone=phone_number,
            type_transaction=transaction_type,
            description=description,
            objet_id=object_id,
            objet_type=object_type,
            status='pending'
        )
        
        try:
            # Données pour l'API KKiaPay
            payment_data = {
                'amount': str(amount),
                'phone': phone_number,
                'sandbox': self.config.sandbox,
                'reason': description or f"TontiFlex - {transaction.get_type_transaction_display()}",
                'webhook': self.config.webhook_url,
                'data': {
                    'transaction_id': str(transaction.id),
                    'reference': transaction.reference_tontiflex,
                    'user_id': user.id,
                    'type': transaction_type
                }
            }
            
            # Appel à l'API KKiaPay
            response = self._make_api_request('POST', '/payment', payment_data)
            
            # Mise à jour de la transaction avec la réponse
            transaction.reference_kkiapay = response.get('transactionId', '')
            transaction.kkiapay_response = response
            transaction.status = 'processing'
            transaction.save()
            
            logger.info(f"✅ Paiement initié avec succès: {transaction.reference_tontiflex}")
            return transaction
            
        except Exception as e:
            # Marquer la transaction comme échouée
            error_msg = str(e)
            logger.error(f"❌ Erreur initiation paiement: {error_msg}")
            
            transaction.mark_as_failed(
                error_code="INITIATION_ERROR",
                error_message=error_msg
            )
            raise
    
    def check_transaction_status(self, transaction: KKiaPayTransaction) -> bool:
        """
        Vérifie le statut d'une transaction auprès de KKiaPay
        
        Args:
            transaction: Transaction à vérifier
            
        Returns:
            bool: True si le statut a changé
        """
        if not transaction.reference_kkiapay:
            logger.warning(f"⚠️ Pas de référence KKiaPay pour {transaction.reference_tontiflex}")
            return False
        
        try:
            # Appel à l'API de vérification
            response = self._make_api_request(
                'GET', 
                f'/transaction/{transaction.reference_kkiapay}/status'
            )
            
            old_status = transaction.status
            new_status = self._map_kkiapay_status(response.get('status', ''))
            
            # Mise à jour si nécessaire
            if new_status != old_status:
                transaction.status = new_status
                transaction.kkiapay_response.update(response)
                
                if new_status == 'success':
                    transaction.processed_at = timezone.now()
                elif new_status in ['failed', 'cancelled']:
                    transaction.error_code = response.get('error_code', 'UNKNOWN')
                    transaction.error_message = response.get('error_message', 'Erreur inconnue')
                    transaction.processed_at = timezone.now()
                
                transaction.save()
                
                logger.info(f"📊 Statut mis à jour: {transaction.reference_tontiflex} {old_status} → {new_status}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erreur vérification statut: {str(e)}")
            return False
    
    def process_webhook(self, webhook_data: Dict) -> Optional[KKiaPayTransaction]:
        """
        Traite un webhook reçu de KKiaPay
        
        Args:
            webhook_data: Données du webhook
            
        Returns:
            KKiaPayTransaction: Transaction mise à jour ou None
        """
        logger.info("📥 Traitement webhook KKiaPay")
        
        try:
            # Validation du webhook
            if not self._validate_webhook(webhook_data):
                logger.error("❌ Webhook KKiaPay invalide")
                return None
            
            # Recherche de la transaction
            transaction_id = webhook_data.get('data', {}).get('transaction_id')
            if not transaction_id:
                logger.error("❌ ID transaction manquant dans webhook")
                return None
            
            transaction = KKiaPayTransaction.objects.get(id=transaction_id)
            
            # Mise à jour avec les données du webhook
            old_status = transaction.status
            new_status = self._map_kkiapay_status(webhook_data.get('status', ''))
            
            transaction.status = new_status
            transaction.webhook_received = True
            transaction.webhook_data = webhook_data
            
            if new_status == 'success':
                transaction.processed_at = timezone.now()
            elif new_status in ['failed', 'cancelled']:
                transaction.error_code = webhook_data.get('error_code', 'WEBHOOK_ERROR')
                transaction.error_message = webhook_data.get('message', 'Erreur webhook')
                transaction.processed_at = timezone.now()
            
            transaction.save()
            
            logger.info(f"✅ Webhook traité: {transaction.reference_tontiflex} {old_status} → {new_status}")
            return transaction
            
        except KKiaPayTransaction.DoesNotExist:
            logger.error(f"❌ Transaction introuvable: {transaction_id}")
            return None
        except Exception as e:
            logger.error(f"❌ Erreur traitement webhook: {str(e)}")
            return None
    
    def _make_api_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """
        Effectue une requête vers l'API KKiaPay
        
        Args:
            method: Méthode HTTP (GET, POST, etc.)
            endpoint: Endpoint de l'API
            data: Données à envoyer
            
        Returns:
            Dict: Réponse de l'API
        """
        url = self.config.get_api_url(endpoint)
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                timeout=self.config.timeout
            )
            
            # Log de la requête
            logger.debug(f"📡 {method} {url} - Status: {response.status_code}")
            
            # Gestion des erreurs HTTP
            if not response.ok:
                error_data = response.json() if response.content else {}
                error_message = error_data.get('message', f'Erreur HTTP {response.status_code}')
                
                logger.error(f"❌ Erreur API KKiaPay: {error_message}")
                raise KKiaPayException(
                    error_message,
                    error_code=str(response.status_code),
                    response_data=error_data
                )
            
            return response.json()
            
        except Exception as e:
            # Gestion des erreurs réseau (RequestException, etc.)
            if 'requests' in str(type(e).__module__):
                logger.error(f"❌ Erreur réseau KKiaPay: {str(e)}")
                raise KKiaPayException(f"Erreur réseau: {str(e)}", error_code="NETWORK_ERROR")
            else:
                raise
    
    def _map_kkiapay_status(self, kkiapay_status: str) -> str:
        """
        Mappe les statuts KKiaPay vers les statuts internes
        
        Args:
            kkiapay_status: Statut retourné par KKiaPay
            
        Returns:
            str: Statut interne correspondant
        """
        status_mapping = {
            'PENDING': 'pending',
            'PROCESSING': 'processing',
            'SUCCESS': 'success',
            'SUCCESSFUL': 'success',
            'FAILED': 'failed',
            'CANCELLED': 'cancelled',
            'REFUNDED': 'refunded',
        }
        
        return status_mapping.get(kkiapay_status.upper(), 'pending')
    
    def _validate_webhook(self, webhook_data: Dict) -> bool:
        """
        Valide un webhook KKiaPay
        
        Args:
            webhook_data: Données du webhook
            
        Returns:
            bool: True si valide
        """
        # TODO: Implémenter la validation de signature
        # Pour l'instant, validation basique
        required_fields = ['status', 'transactionId']
        return all(field in webhook_data for field in required_fields)


# Instance globale du service (sera initialisée à la demande)
_kkiapay_service = None

def get_kkiapay_service():
    """Retourne l'instance du service KKiaPay (lazy loading)"""
    global _kkiapay_service
    if _kkiapay_service is None:
        _kkiapay_service = KKiaPayService()
    return _kkiapay_service

# Alias pour compatibilité
kkiapay_service = get_kkiapay_service
