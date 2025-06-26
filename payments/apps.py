"""
Configuration Django pour le module Payments KKiaPay
"""
from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'payments'
    verbose_name = 'Paiements KKiaPay'
    
    def ready(self):
        """
        Configuration du module lors du démarrage de Django
        """
        pass
