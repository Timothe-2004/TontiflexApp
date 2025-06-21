"""
Services pour l'intégration Mobile Money dans TontiFlex.
Support principal pour MTN Mobile Money avec architecture extensible.
"""

import os
import uuid
import json
import requests
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, List, Tuple, Any
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

from .models import TransactionMobileMoney, OperateurMobileMoney
from .services_mtn_withdrawals import MTNWithdrawalsV1Service
from .services_mtn_new_api_complete import MTNConformeAPIService
from .exceptions import (
    MobileMoneyServiceException,
    OperateurNonSupporte,
    MontantInvalide,
    NumeroTelephoneInvalide,
    ErreurAPI,
    TransactionExpire
)

logger = logging.getLogger(__name__)


class MobileMoneyService:
    """
    Service principal pour la gestion des paiements Mobile Money.
    Coordonne les différents adaptateurs d'opérateurs.
    """
    def __init__(self):
        # Services MTN conformes aux Swagger officiels
        self.mtn_official_service = MTNConformeAPIService()
        self.withdrawals_service = MTNWithdrawalsV1Service()
        
        # Adaptateurs conformes (MTN uniquement selon spécifications officielles)
        self.adapters = {
            'MTN': MTNAdapter(),  # Service conforme MTN Payments V1
        }

    def generer_lien_paiement(self, montant, numero_telephone, description, correlator_id=None, demande=None):
        """
        Génère un lien de paiement MTN Payments V1 via le service officiel.
        """
        try:
            return self.mtn_official_service.generer_lien_paiement(
                montant=montant,
                numero_telephone=numero_telephone,
                description=description,
                correlator_id=correlator_id,
                demande=demande
            )
        except Exception as e:
            logger.error(f"Erreur génération lien paiement: {e}")
            raise MobileMoneyServiceException(f"Erreur génération lien paiement: {e}")

    def initier_paiement_ussd(self, montant, numero_telephone, description, correlator_id=None, demande=None):
        """
        Initie un paiement MTN avec notification USSD directement sur le téléphone.
        """
        try:
            logger.info(f"[MOBILE_MONEY] Initiation paiement USSD pour {numero_telephone}, montant={montant}")
            
            # Utilisation du service MTN officiel
            result = self.mtn_official_service.initier_paiement_ussd(
                montant=montant,
                numero_telephone=numero_telephone,
                description=description,
                correlator_id=correlator_id,
                demande=demande
            )
            
            logger.info(f"[MOBILE_MONEY] Paiement USSD initié: {result.get('transaction_id')}")
            return result
                
        except Exception as e:
            logger.error(f"[MOBILE_MONEY] Erreur initiation paiement USSD: {e}")
            return {
                'success': False,
                'error': f'Erreur lors de l\'initiation du paiement USSD: {str(e)}'
            }

    def initier_retrait(self, correlator_id, customer_id, resource, amount, units='XOF', description='', external_reference=None, calling_system='ECW', target_system='ECW', status='Pending', additional_information=None):
        """
        Initie un retrait via MTN Withdrawals V1.
        """
        return self.withdrawals_service.create_withdrawal(
            correlator_id=correlator_id,
            customer_id=customer_id,
            resource=resource,
            amount=amount,
            units=units,
            description=description,
            external_reference=external_reference,
            calling_system=calling_system,
            target_system=target_system,
            status=status,
            additional_information=additional_information
        )

    def detecter_operateur(self, numero_telephone: str) -> str:
        """
        Détecte l'opérateur à partir du numéro de téléphone.
        
        Args:
            numero_telephone: Numéro au format international (+229...)
            
        Returns:
            Code de l'opérateur (MTN uniquement - conforme aux APIs officielles)
            
        Raises:
            OperateurNonSupporte: Si l'opérateur n'est pas supporté
        """
        # Nettoyer le numéro
        numero_clean = numero_telephone.replace('+', '').replace(' ', '').replace('-', '')
        
        # Préfixes Bénin - MTN uniquement (conforme aux spécifications Swagger MTN)
        # MTN: 51, 60, 61, 62, 66, 67, 69, 90, 91, 96, 97
        prefixes_mtn = [
            '2290151', '2290160', '2290161', '2290162', '2290166', 
            '2290167', '2290169', '2290190', '2290191', '2290196', '2290197'
        ]
        
        for prefix in prefixes_mtn:
            if numero_clean.startswith(prefix):
                return 'MTN'
        
        # Seul MTN est supporté selon les spécifications Swagger officielles        
        raise OperateurNonSupporte(f"Seuls les numéros MTN sont supportés. Numéro non reconnu: {numero_telephone}")

    def initier_paiement(
            self, 
            client_id: int,
            numero_telephone: str, 
            montant: Decimal, 
            type_transaction: str = 'paiement',
            description: str = '',
            metadata: Dict = None
        ) -> TransactionMobileMoney:
        """
        Initie un paiement Mobile Money.
        
        Args:
            client_id: ID du client effectuant le paiement
            numero_telephone: Numéro de téléphone du payeur
            montant: Montant à payer
            type_transaction: Type de transaction
            description: Description du paiement
            metadata: Métadonnées additionnelles
            
        Returns:
            TransactionMobileMoney: Instance de la transaction créée
            
        Raises:
            OperateurNonSupporte: Si l'opérateur n'est pas supporté
            MontantInvalide: Si le montant est invalide
            NumeroTelephoneInvalide: Si le numéro est invalide
        """
        transaction = None
        try:
            logger.info(f"Initiation paiement: client={client_id}, montant={montant}, tel={numero_telephone}")
            
            # Validation du montant
            if montant <= 0:
                raise MontantInvalide("Le montant doit être positif")
              
            # Détection de l'opérateur
            operateur_code = self.detecter_operateur(numero_telephone)
            logger.info(f"Opérateur détecté: {operateur_code}")
            
            # Récupération de l'opérateur
            operateur = OperateurMobileMoney.objects.get(code=operateur_code)
            
            # Création de la transaction
            transaction = TransactionMobileMoney.objects.create(
                client_id=str(client_id),
                numero_telephone=numero_telephone,
                montant=montant,
                devise='XOF',
                type_transaction=type_transaction,
                description=description,
                reference_interne=self._generer_reference(type_transaction),
                operateur=operateur,
                statut='initie',
                metadata=metadata or {}
            )
            
            # Initiation via le service MTN officiel
            result = self.mtn_official_service.initier_paiement_ussd(
                montant=float(montant),
                numero_telephone=numero_telephone,
                description=description,
                correlator_id=transaction.reference_interne,
                demande=None
            )
            
            if result.get('success'):
                transaction.statut = 'en_attente'
                transaction.reference_operateur = result.get('transaction_id')
                transaction.reponse_operateur = result
                transaction.save()
                
                logger.info(f"Paiement MTN initié avec succès: {transaction.reference_interne}")
                return transaction
            else:
                transaction.statut = 'echec'
                transaction.message_erreur = result.get('error', 'Erreur inconnue')
                transaction.save()
                raise ErreurAPI(f"Erreur MTN: {result.get('error')}")
            
        except Exception as e:
            logger.error(f"Erreur initiation paiement: {e}")
            if transaction:
                transaction.statut = 'echec'
                transaction.message_erreur = str(e)
                transaction.save()
            raise

    def _generer_reference(self, type_transaction: str) -> str:
        """Génère une référence unique pour la transaction."""
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        return f"TF_{type_transaction.upper()}_{timestamp}_{unique_id}"

    def verifier_statut(self, reference: str, type_reference: str = 'interne') -> Dict:
        """
        Vérifie le statut d'une transaction.
        
        Args:
            reference: Référence de la transaction (interne ou opérateur)
            type_reference: Type de référence ('interne' ou 'operateur')
            
        Returns:
            Dict: Statut et détails de la transaction
        """
        try:
            # Récupération de la transaction
            if type_reference == 'interne':
                transaction = TransactionMobileMoney.objects.get(reference_interne=reference)
            else:
                transaction = TransactionMobileMoney.objects.get(reference_operateur=reference)
            
            # Si déjà terminée, retourner le statut actuel
            if transaction.statut in ['succes', 'echec', 'expire', 'annule']:
                return self._formater_statut_response(transaction)
            
            # Vérification via le service MTN officiel
            statut_result = self.mtn_official_service.verifier_statut_paiement(
                transaction.reference_operateur or transaction.reference_interne
            )
              # Mise à jour du statut
            ancien_statut = transaction.statut
            if statut_result.get('success'):
                nouveau_statut = statut_result.get('status', transaction.statut)
                transaction.statut = nouveau_statut
                transaction.reponse_operateur = statut_result
                
                if transaction.statut == 'succes':
                    transaction.date_completion = timezone.now()
                
                transaction.save()
                
                # Log si changement de statut
                if ancien_statut != transaction.statut:
                    logger.info(f"Statut mis à jour: {reference} {ancien_statut} -> {transaction.statut}")
            
            return self._formater_statut_response(transaction)
            
        except TransactionMobileMoney.DoesNotExist:
            raise MobileMoneyServiceException(f"Transaction non trouvée: {reference}")
        except Exception as e:
            logger.error(f"Erreur vérification statut: {e}")
            raise MobileMoneyServiceException(f"Erreur vérification: {e}")
    
    def traiter_webhook(self, request, operateur_code: str) -> Dict:
        """
        Traite un webhook reçu d'un opérateur.
        """
        try:
            logger.info(f"Traitement webhook {operateur_code}")
            
            if operateur_code == 'MTN':
                # Traitement via le service MTN officiel
                return self.mtn_official_service.traiter_webhook_paiement(request)
            else:
                raise OperateurNonSupporte(f"Webhook {operateur_code} non supporté")
            
        except Exception as e:
            logger.error(f"Erreur traitement webhook: {e}")
            raise MobileMoneyServiceException(f"Erreur webhook: {e}")
    
    def annuler_transaction(self, reference_interne: str) -> bool:
        """
        Annule une transaction en attente.
        """
        try:
            transaction = TransactionMobileMoney.objects.get(reference_interne=reference_interne)
            
            if transaction.statut not in ['initie', 'en_attente']:
                raise MobileMoneyServiceException("Transaction non annulable")
            
            transaction.statut = 'annule'
            transaction.save()
            
            logger.info(f"Transaction annulée: {reference_interne}")
            return True
            
        except TransactionMobileMoney.DoesNotExist:
            raise MobileMoneyServiceException(f"Transaction non trouvée: {reference_interne}")
    
    def _formater_statut_response(self, transaction: TransactionMobileMoney) -> Dict:
        """Formate la réponse de statut."""
        return {
            'reference_interne': transaction.reference_interne,
            'reference_operateur': transaction.reference_operateur,
            'statut': transaction.statut,
            'montant': float(transaction.montant),
            'devise': transaction.devise,
            'date_creation': transaction.date_creation.isoformat(),
            'date_completion': transaction.date_completion.isoformat() if transaction.date_completion else None,
            'description': transaction.description,
            'operateur': transaction.operateur.code if transaction.operateur else None,
            'message_erreur': transaction.message_erreur
        }

    def verifier_statut_avec_polling_et_mise_a_jour(self, transaction: TransactionMobileMoney, 
                                                   max_attempts: int = 12, interval_seconds: int = 5) -> Dict[str, Any]:
        """
        Vérifie le statut d'une transaction avec polling automatique et mise à jour en BDD.
        
        Args:
            transaction: Instance TransactionMobileMoney à vérifier
            max_attempts: Nombre maximum de tentatives (défaut: 12 = 1 minute)
            interval_seconds: Intervalle entre tentatives (défaut: 5 secondes)
            
        Returns:
            Dict avec le résultat final du polling
        """
        try:
            logger.info(f"[MOBILE_MONEY] Début polling avec mise à jour: {transaction.reference_interne}")
            
            # Utiliser la référence opérateur si disponible, sinon référence interne
            payment_reference = transaction.reference_operateur or transaction.reference_interne
            
            # Effectuer le polling via le service MTN
            result = self.mtn_official_service.verifier_statut_avec_polling(
                payment_reference=payment_reference,
                max_attempts=max_attempts,
                interval_seconds=interval_seconds
            )
            
            # Mettre à jour la transaction en base
            ancien_statut = transaction.statut
            
            if result['success']:
                nouveau_statut = result['status']
                
                # Mise à jour des champs de la transaction
                transaction.statut = nouveau_statut
                transaction.reponse_operateur = result
                
                # Si transaction terminée avec succès
                if nouveau_statut == 'succes':
                    transaction.date_completion = timezone.now()
                    
                # Sauvegarder les modifications
                transaction.save()
                
                # Log des changements
                if ancien_statut != nouveau_statut:
                    logger.info(f"[MOBILE_MONEY] ✅ Statut mis à jour: {transaction.reference_interne} "
                              f"{ancien_statut} -> {nouveau_statut} (après {result.get('polling_attempts', 0)} tentatives)")
                
                return {
                    'success': True,
                    'transaction_id': str(transaction.id),
                    'reference_interne': transaction.reference_interne,
                    'ancien_statut': ancien_statut,
                    'nouveau_statut': nouveau_statut,
                    'statut_change': ancien_statut != nouveau_statut,
                    'polling_info': {
                        'attempts': result.get('polling_attempts', 0),
                        'duration': result.get('polling_duration', 0)
                    },
                    'details': result
                }
            else:
                # Erreur lors du polling
                transaction.statut = 'echec'
                transaction.message_erreur = result.get('error', 'Erreur polling statut')
                transaction.reponse_operateur = result
                transaction.save()
                
                logger.error(f"[MOBILE_MONEY] ❌ Échec polling: {transaction.reference_interne} - {result.get('error')}")
                
                return {
                    'success': False,
                    'transaction_id': str(transaction.id),
                    'reference_interne': transaction.reference_interne,
                    'ancien_statut': ancien_statut,
                    'nouveau_statut': 'echec',
                    'statut_change': True,
                    'error': result.get('error'),
                    'polling_info': {
                        'attempts': result.get('polling_attempts', 0),
                        'duration': result.get('polling_duration', 0)
                    },
                    'details': result
                }
                
        except Exception as e:
            logger.error(f"[MOBILE_MONEY] Erreur polling avec mise à jour: {e}")
            
            # Marquer la transaction comme échouée
            transaction.statut = 'echec'
            transaction.message_erreur = f'Erreur polling: {str(e)}'
            transaction.save()
            
            return {
                'success': False,
                'transaction_id': str(transaction.id),
                'error': str(e),
                'nouveau_statut': 'echec'
            }
            
class MTNAdapter:
    """
    Adaptateur pour l'API MTN Mobile Money.
    Implémente l'intégration avec l'API officielle MTN.
    """
    
    def __init__(self):
        self.environment = os.getenv('MTN_ENVIRONMENT', 'sandbox')
        self.base_url = os.getenv('MTN_API_BASE_URL', 'https://api.mtn.com/v1')
        self.consumer_key = os.getenv('MTN_CONSUMER_KEY')
        self.consumer_secret = os.getenv('MTN_CONSUMER_SECRET')
        self.api_user = os.getenv('MTN_API_USER')
        self.api_key = os.getenv('MTN_API_KEY')
        self.subscription_key = os.getenv('MTN_SUBSCRIPTION_KEY')
        self.callback_url = os.getenv('MTN_CALLBACK_URL')
        
        # Validation des variables d'environnement
        if not all([self.consumer_key, self.consumer_secret, self.api_user, self.api_key]):
            raise MobileMoneyServiceException("Configuration MTN incomplète - vérifiez le fichier .env")
    
    def get_operateur(self) -> OperateurMobileMoney:
        """Récupère ou crée l'opérateur MTN."""
        operateur, created = OperateurMobileMoney.objects.get_or_create(
            code='MTN',
            defaults={
                'nom': 'MTN Mobile Money',
                'api_base_url': self.base_url,
                'prefixes_telephone': ['2290196', '2290197', '2290161', '2290162', '2290166', '2290167', '2290169', '2290151', '2290152', '2290190'],
                'frais_fixe': Decimal('0.00'),
                'frais_pourcentage': Decimal('1.50'),  # 1.5%
                'montant_minimum': Decimal('100.00'),
                'montant_maximum': Decimal('2000000.00'),
                'statut': 'actif'
            }
        )
        return operateur


class MobileMoneyTontineService:
    """
    Service spécialisé pour les transactions Mobile Money des tontines.
    """
    def __init__(self):
        self.mobile_money_service = MobileMoneyService()
        # Utilisation du service MTN conforme au Swagger officiel
        self.mtn_service = MTNConformeAPIService()

    def initier_paiement_adhesion_mtn_ussd(self, montant, numero_telephone, description, correlator_id=None, demande=None):
        """
        Initie un paiement MTN Mobile Money avec notification USSD pour adhésion.
        """
        try:
            logger.info(f"[TONTINE] Initiation paiement adhésion USSD pour {numero_telephone}, montant={montant}")
            
            # Délégation vers le service MTN officiel
            result = self.mtn_service.initier_paiement_ussd(
                montant=montant,
                numero_telephone=numero_telephone,
                description=description,
                correlator_id=correlator_id,
                demande=demande
            )
            
            if result.get('success'):
                logger.info(f"[TONTINE] Paiement adhésion USSD initié: {result.get('transaction_id')}")
                
                return {
                    'success': True,
                    'transaction_id': result['transaction_id'],
                    'correlator_id': result['correlator_id'],
                    'status': result['status'],
                    'message': 'Paiement d\'adhésion initié. Vérifiez votre téléphone pour la notification USSD.',
                    'payment_response': result
                }
            else:
                logger.error(f"[TONTINE] Échec initiation paiement adhésion: {result.get('error')}")
                return result
                
        except Exception as e:
            logger.error(f"[TONTINE] Erreur initiation paiement adhésion USSD: {e}")
            return {
                'success': False,
                'error': f'Erreur lors de l\'initiation du paiement d\'adhésion USSD: {str(e)}'
            }

    def initier_cotisation_tontine(self, user, tontine, montant, numero_telephone, description=None):
        """
        Initie une cotisation tontine via Mobile Money.
        """
        try:
            # Validation préalable
            if not self._peut_cotiser(user, tontine):
                return {
                    'success': False,
                    'message': 'Vous ne pouvez pas cotiser à cette tontine'
                }
            
            # Vérification du montant
            if montant < tontine.montant_cotisation:
                return {
                    'success': False,
                    'message': f'Le montant minimum est de {tontine.montant_cotisation} FCFA'
                }
            
            # Création de la description
            if not description:
                description = f'Cotisation tontine {tontine.nom} - {montant} FCFA'
            
            # Initiation via le service Mobile Money
            transaction = self.mobile_money_service.initier_paiement(
                client_id=user.id,
                montant=Decimal(str(montant)),
                numero_telephone=numero_telephone,
                type_transaction='cotisation_tontine',
                description=description,
                metadata={
                    'tontine_id': str(tontine.id),
                    'user_id': str(user.id),
                    'type': 'cotisation_tontine'
                }
            )
            
            # Création de la cotisation en base
            from tontines.models.cotisation import Cotisation
            cotisation = Cotisation.objects.create(
                tontine=tontine,
                user=user,
                montant=montant,
                statut='en_attente',
                reference_paiement=transaction.reference_interne,
                mode_paiement='mobile_money'
            )
            
            return {
                'success': True,
                'reference': transaction.reference_interne,
                'transaction_id': str(transaction.id),
                'cotisation_id': str(cotisation.id),
                'instructions': 'Veuillez confirmer le paiement sur votre téléphone'
            }
            
        except Exception as e:
            logger.error(f"Erreur initiation cotisation tontine: {e}")
            return {
                'success': False,
                'message': 'Erreur lors de l\'initiation du paiement'
            }

    def verifier_statut_transaction(self, transaction_id):
        """
        Vérifie le statut d'une transaction de cotisation.
        """
        try:
            transaction = TransactionMobileMoney.objects.get(id=transaction_id)
            statut_result = self.mobile_money_service.verifier_statut(
                transaction.reference_interne, 'interne'
            )
            
            # Mise à jour de la cotisation si nécessaire
            if statut_result['statut'] == 'succes':
                self._finaliser_cotisation(transaction)
            
            return {
                'statut': statut_result['statut'],
                'details': statut_result
            }
            
        except TransactionMobileMoney.DoesNotExist:
            return {
                'statut': 'non_trouve',
                'message': 'Transaction non trouvée'
            }
        except Exception as e:
            logger.error(f"Erreur vérification statut: {e}")
            return {
                'statut': 'erreur',
                'message': 'Erreur lors de la vérification'
            }

    def calculer_frais(self, montant, numero_telephone):
        """
        Calcule les frais Mobile Money pour une cotisation.
        """
        try:
            # Détection de l'opérateur
            operateur_code = self.mobile_money_service.detecter_operateur(numero_telephone)
            
            # Récupération de l'opérateur
            operateur = OperateurMobileMoney.objects.get(code=operateur_code)
            
            # Calcul des frais
            frais = operateur.frais_fixe + (Decimal(str(montant)) * operateur.frais_pourcentage / 100)
            montant_total = Decimal(str(montant)) + frais
            
            return {
                'success': True,
                'frais': float(frais),
                'montant_total': float(montant_total),
                'operateur': operateur_code,
                'details': {
                    'frais_fixe': float(operateur.frais_fixe),
                    'frais_pourcentage': float(operateur.frais_pourcentage),
                    'frais_calcules': float(frais)
                }
            }
            
        except OperateurMobileMoney.DoesNotExist:
            return {
                'success': False,
                'message': 'Opérateur non supporté'
            }
        except Exception as e:
            logger.error(f"Erreur calcul frais: {e}")
            return {
                'success': False,
                'message': 'Erreur lors du calcul des frais'
            }
    
    def _peut_cotiser(self, user, tontine):
        """
        Vérifie si un utilisateur peut cotiser à une tontine.
        """
        # Vérification que l'utilisateur est membre de la tontine
        from tontines.models.adhesion_workflow import WorkflowAdhesion
        try:
            adhesion = WorkflowAdhesion.objects.get(
                tontine=tontine,
                user=user,
                statut='complete'
            )
            return True
        except WorkflowAdhesion.DoesNotExist:
            return False
    
    def _finaliser_cotisation(self, transaction):
        """
        Finalise une cotisation après paiement réussi.
        """
        try:
            from tontines.models.cotisation import Cotisation
            cotisation = Cotisation.objects.get(
                reference_paiement=transaction.reference_interne
            )
            
            cotisation.statut = 'validee'
            cotisation.date_paiement = timezone.now()
            cotisation.save()
            
            logger.info(f"Cotisation finalisée: {cotisation.id}")
            
        except Cotisation.DoesNotExist:
            logger.error(f"Cotisation non trouvée pour transaction: {transaction.reference_interne}")
        except Exception as e:
            logger.error(f"Erreur finalisation cotisation: {e}")
