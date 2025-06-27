"""
Service de migration des transactions Mobile Money vers KKiaPay
============================================================

Ce service gère la migration complète du système Mobile Money vers KKiaPay
pour la mise en production.
"""

import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import KKiaPayTransaction
from .services import KKiaPayService

logger = logging.getLogger(__name__)


class MigrationService:
    """
    Service pour migrer complètement vers KKiaPay
    """
    
    def __init__(self):
        self.kkiapay_service = KKiaPayService()
    
    @transaction.atomic
    def create_tontine_withdrawal_transaction(self, retrait_data):
        """
        Créer une transaction KKiaPay pour un retrait de tontine
        
        Args:
            retrait_data (dict): Données du retrait
                - user: Utilisateur
                - montant: Montant à retirer
                - telephone: Numéro de téléphone
                - retrait_id: ID du retrait
                - description: Description
        
        Returns:
            KKiaPayTransaction: Transaction créée
        """
        try:
            # Générer référence unique TontiFlex
            reference = f"RETRAIT_TONT_{retrait_data['retrait_id']}"
            
            # Créer la transaction KKiaPay
            transaction_kkia = KKiaPayTransaction.objects.create(
                reference_tontiflex=reference,
                type_transaction='retrait_tontine',
                status='pending',
                montant=retrait_data['montant'],
                devise='XOF',
                user=retrait_data['user'],
                numero_telephone=retrait_data['telephone'],
                description=retrait_data.get('description', f"Retrait tontine - {reference}")
            )
            
            logger.info(f"Transaction KKiaPay créée pour retrait: {reference}")
            return transaction_kkia
            
        except Exception as e:
            logger.error(f"Erreur création transaction retrait: {e}")
            raise
    
    @transaction.atomic
    def create_tontine_adhesion_transaction(self, adhesion_data):
        """
        Créer une transaction KKiaPay pour l'adhésion à une tontine
        
        Args:
            adhesion_data (dict): Données d'adhésion
                - user: Utilisateur
                - montant: Montant des frais d'adhésion
                - telephone: Numéro de téléphone
                - adhesion_id: ID de l'adhésion
                - description: Description
        
        Returns:
            KKiaPayTransaction: Transaction créée
        """
        try:
            # Générer référence unique TontiFlex
            reference = f"ADHE_TONT_{adhesion_data['adhesion_id']}"
            
            # Créer la transaction KKiaPay
            transaction_kkia = KKiaPayTransaction.objects.create(
                reference_tontiflex=reference,
                type_transaction='adhesion_tontine',
                status='pending',
                montant=adhesion_data['montant'],
                devise='XOF',
                user=adhesion_data['user'],
                numero_telephone=adhesion_data['telephone'],
                description=adhesion_data.get('description', f"Frais adhésion tontine - {reference}"),
                metadata={
                    'adhesion_id': adhesion_data['adhesion_id'],
                    'type': 'frais_adhesion_tontine'
                }
            )
            
            logger.info(f"Transaction KKiaPay créée pour adhésion: {reference}")
            return transaction_kkia
            
        except Exception as e:
            logger.error(f"Erreur création transaction adhésion: {e}")
            raise

    @transaction.atomic
    def create_tontine_contribution_transaction(self, cotisation_data):
        """
        Créer une transaction KKiaPay pour une cotisation de tontine
        
        Args:
            cotisation_data (dict): Données de cotisation
        
        Returns:
            KKiaPayTransaction: Transaction créée
        """
        try:
            reference = f"COTIS_TONT_{cotisation_data['cotisation_id']}"
            
            transaction_kkia = KKiaPayTransaction.objects.create(
                reference_tontiflex=reference,
                type_transaction='cotisation_tontine',
                status='pending',
                montant=cotisation_data['montant'],
                devise='XOF',
                user=cotisation_data['user'],
                numero_telephone=cotisation_data['telephone'],
                description=cotisation_data.get('description', f"Cotisation tontine - {reference}")
            )
            
            logger.info(f"Transaction KKiaPay créée pour cotisation: {reference}")
            return transaction_kkia
            
        except Exception as e:
            logger.error(f"Erreur création transaction cotisation: {e}")
            raise
    
    @transaction.atomic
    def create_savings_transaction(self, epargne_data):
        """
        Créer une transaction KKiaPay pour l'épargne
        
        Args:
            epargne_data (dict): Données d'épargne
        
        Returns:
            KKiaPayTransaction: Transaction créée
        """
        try:
            transaction_type = epargne_data['type']  # 'depot_epargne' ou 'retrait_epargne'
            reference = f"EPARGNE_{transaction_type.upper()}_{epargne_data['operation_id']}"
            
            transaction_kkia = KKiaPayTransaction.objects.create(
                reference_tontiflex=reference,
                type_transaction=transaction_type,
                status='pending',
                montant=epargne_data['montant'],
                devise='XOF',
                user=epargne_data['user'],
                numero_telephone=epargne_data['telephone'],
                description=epargne_data.get('description', f"Transaction épargne - {reference}")
            )
            
            logger.info(f"Transaction KKiaPay créée pour épargne: {reference}")
            return transaction_kkia
            
        except Exception as e:
            logger.error(f"Erreur création transaction épargne: {e}")
            raise
    
    def initiate_payment(self, transaction_kkia):
        """
        Initier le paiement via KKiaPay
        
        Args:
            transaction_kkia (KKiaPayTransaction): Transaction à traiter
        
        Returns:
            dict: Résultat de l'initiation
        """
        try:
            # Appeler le service KKiaPay pour initier le paiement
            result = self.kkiapay_service.initiate_payment({
                'amount': float(transaction_kkia.montant),
                'currency': transaction_kkia.devise,
                'phone': transaction_kkia.numero_telephone,
                'reference': transaction_kkia.reference_tontiflex,
                'description': transaction_kkia.description,
                'type': transaction_kkia.type_transaction
            })
            
            if result.get('success'):
                # Mettre à jour la transaction avec la réponse KKiaPay
                transaction_kkia.status = 'processing'
                transaction_kkia.reference_kkiapay = result.get('transaction_id')
                transaction_kkia.kkiapay_response = result
                transaction_kkia.save()
                
                logger.info(f"Paiement KKiaPay initié: {transaction_kkia.reference_tontiflex}")
            else:
                transaction_kkia.status = 'failed'
                transaction_kkia.message_erreur = result.get('error', 'Erreur inconnue')
                transaction_kkia.save()
                
                logger.error(f"Échec initiation paiement: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur initiation paiement KKiaPay: {e}")
            transaction_kkia.status = 'failed'
            transaction_kkia.message_erreur = str(e)
            transaction_kkia.save()
            raise
    
    def verify_transaction(self, transaction_kkia):
        """
        Vérifier le statut d'une transaction KKiaPay
        
        Args:
            transaction_kkia (KKiaPayTransaction): Transaction à vérifier
        
        Returns:
            dict: Statut de la transaction
        """
        try:
            if not transaction_kkia.reference_kkiapay:
                return {'success': False, 'error': 'Pas de référence KKiaPay'}
            
            # Vérifier via l'API KKiaPay
            result = self.kkiapay_service.verify_transaction(
                transaction_kkia.reference_kkiapay
            )
            
            if result.get('success'):
                status = result.get('status')
                
                if status == 'SUCCESS':
                    transaction_kkia.status = 'success'
                    transaction_kkia.date_completion = timezone.now()
                elif status == 'FAILED':
                    transaction_kkia.status = 'failed'
                    transaction_kkia.message_erreur = result.get('message', 'Transaction échouée')
                else:
                    transaction_kkia.status = 'processing'
                
                transaction_kkia.kkiapay_response = result
                transaction_kkia.save()
                
                logger.info(f"Statut transaction vérifié: {transaction_kkia.reference_tontiflex} -> {status}")
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur vérification transaction: {e}")
            raise


# Instance globale du service de migration
migration_service = MigrationService()
