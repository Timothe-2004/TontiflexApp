"""
Configuration centralisée KKiaPay pour TontiFlex
===============================================

Centralise toute la configuration KKiaPay en un seul endroit.
Mode SANDBOX activé pour développement.

Documentation : https://kkiapay.me/kkiapay-integration/?lang=en
"""
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class KKiaPayConfig:
    """
    Configuration centralisée pour KKiaPay
    """
    
    def __init__(self):
        """Initialise la configuration KKiaPay"""
        self.sandbox = getattr(settings, 'KKIAPAY_SANDBOX', True)
        self.public_key = getattr(settings, 'KKIAPAY_PUBLIC_KEY', '')
        self.private_key = getattr(settings, 'KKIAPAY_PRIVATE_KEY', '')
        self.secret_key = getattr(settings, 'KKIAPAY_SECRET_KEY', '')
        self.base_url = getattr(settings, 'KKIAPAY_BASE_URL', '')
        self.webhook_url = getattr(settings, 'KKIAPAY_WEBHOOK_URL', '')
        self.webhook_secret = getattr(settings, 'KKIAPAY_WEBHOOK_SECRET', '')
        self.timeout = getattr(settings, 'KKIAPAY_TIMEOUT', 30)
        self.max_retries = getattr(settings, 'KKIAPAY_MAX_RETRIES', 3)
        self.currency = getattr(settings, 'KKIAPAY_CURRENCY', 'XOF')
        
        # Validation de la configuration
        self._validate_config()
    
    def _validate_config(self):
        """Valide la configuration KKiaPay"""
        if not self.public_key:
            logger.warning("⚠️ KKIAPAY_PUBLIC_KEY non configuré")
        
        if not self.private_key:
            logger.warning("⚠️ KKIAPAY_PRIVATE_KEY non configuré")
        
        if not self.secret_key:
            logger.warning("⚠️ KKIAPAY_SECRET_KEY non configuré")
        
        if self.sandbox:
            logger.info("🧪 Mode SANDBOX KKiaPay activé")
        else:
            logger.info("🚀 Mode LIVE KKiaPay activé")
    
    def is_configured(self):
        """Vérifie si KKiaPay est correctement configuré"""
        return bool(self.public_key and self.private_key and self.secret_key)
    
    def get_api_url(self, endpoint=""):
        """Retourne l'URL complète de l'API KKiaPay"""
        base = self.base_url.rstrip('/')
        endpoint = endpoint.lstrip('/')
        return f"{base}/{endpoint}" if endpoint else base
    
    def __str__(self):
        mode = "SANDBOX" if self.sandbox else "LIVE"
        status = "✅ Configuré" if self.is_configured() else "❌ Non configuré"
        return f"KKiaPay {mode} - {status}"


# Instance globale de configuration
kkiapay_config = KKiaPayConfig()
