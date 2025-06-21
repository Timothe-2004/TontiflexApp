"""
Service de simulation MTN pour les tests en développement.
Permet de simuler les réponses MTN sans faire de vraies transactions.
"""

import uuid
import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings


class MTNSimulationService:
    """
    Service de simulation MTN pour le développement.
    Remplace les vraies API MTN par des simulations contrôlées.
    """
    
    def __init__(self):
        self.simulation_enabled = getattr(settings, 'MTN_SIMULATION_MODE', settings.DEBUG)
        self.fake_transactions = {}
        self.response_delay = 1  # Délai pour simuler la latence réseau
        
        # Scénarios de test prédéfinis
        self.test_scenarios = {
            'success_immediate': {
                'initial_status': 'SUCCESSFUL',
                'final_status': 'SUCCESSFUL',
                'delay_seconds': 0
            },
            'success_delayed': {
                'initial_status': 'PENDING',
                'final_status': 'SUCCESSFUL',
                'delay_seconds': 10
            },
            'failure_funds': {
                'initial_status': 'PENDING',
                'final_status': 'FAILED',
                'status_code': '6001',
                'delay_seconds': 5
            },
            'timeout': {
                'initial_status': 'PENDING',
                'final_status': 'PENDING',
                'delay_seconds': 60
            }
        }
    
    def simulate_oauth_token(self) -> Dict[str, Any]:
        """Simule l'obtention d'un token OAuth."""
        if not self.simulation_enabled:
            raise ValueError("Simulation non activée")
        
        return {
            'access_token': f'FAKE_TOKEN_{uuid.uuid4().hex[:16]}',
            'token_type': 'Bearer',
            'expires_in': 3600
        }
    
    def simulate_payment_request(self, payment_request: Dict[str, Any], 
                                scenario: str = 'success_delayed') -> Dict[str, Any]:
        """
        Simule une requête de paiement MTN.
        
        Args:
            payment_request: Requête de paiement conforme à l'API MTN
            scenario: Scénario de test à utiliser
        
        Returns:
            Réponse simulée de MTN
        """
        if not self.simulation_enabled:
            raise ValueError("Simulation non activée")
        
        # Simuler délai réseau
        time.sleep(self.response_delay)
        
        payment_reference = payment_request.get('paymentReference', f'SIM_{uuid.uuid4().hex[:8]}')
        scenario_config = self.test_scenarios.get(scenario, self.test_scenarios['success_delayed'])
        
        # Créer la transaction simulée
        transaction_data = {
            'paymentReference': payment_reference,
            'transactionId': f'MTN_SIM_{uuid.uuid4().hex[:8]}',
            'externalTransactionId': payment_request.get('externalTransactionId'),
            'status': scenario_config['initial_status'],
            'statusCode': scenario_config.get('status_code', '202'),
            'statusMessage': self._get_status_message(scenario_config['initial_status']),
            'amount': payment_request['totalAmount'],
            'payer': payment_request['payer'],
            'created_at': timezone.now(),
            'scenario': scenario,
            'scenario_config': scenario_config
        }
        
        # Stocker la transaction simulée
        self.fake_transactions[payment_reference] = transaction_data
        
        # Programmer le changement de statut si nécessaire
        if scenario_config['delay_seconds'] > 0:
            self._schedule_status_change(payment_reference, scenario_config)
        
        # Retourner la réponse initiale
        return {
            'paymentReference': payment_reference,
            'transactionId': transaction_data['transactionId'],
            'externalTransactionId': transaction_data['externalTransactionId'],
            'statusCode': transaction_data['statusCode'],
            'statusMessage': transaction_data['statusMessage'],
            'simulationInfo': {
                'scenario': scenario,
                'willChangeTo': scenario_config['final_status'],
                'delaySeconds': scenario_config['delay_seconds']
            }
        }
    
    def simulate_status_check(self, payment_reference: str) -> Dict[str, Any]:
        """
        Simule la vérification de statut d'une transaction.
        
        Args:
            payment_reference: Référence du paiement
            
        Returns:
            Statut simulé de la transaction
        """
        if not self.simulation_enabled:
            raise ValueError("Simulation non activée")
        
        # Simuler délai réseau
        time.sleep(self.response_delay)
        
        # Chercher la transaction simulée
        if payment_reference not in self.fake_transactions:
            return {
                'success': False,
                'statusCode': '404',
                'message': 'Transaction not found',
                'simulation': True
            }
        
        transaction = self.fake_transactions[payment_reference]
        scenario_config = transaction['scenario_config']
        
        # Vérifier si le statut doit changer
        elapsed_time = (timezone.now() - transaction['created_at']).total_seconds()
        
        if elapsed_time >= scenario_config['delay_seconds']:
            # Mettre à jour le statut
            transaction['status'] = scenario_config['final_status']
            transaction['statusCode'] = scenario_config.get('final_status_code', '0000')
            transaction['statusMessage'] = self._get_status_message(scenario_config['final_status'])
            transaction['updated_at'] = timezone.now()
        
        # Construire la réponse conforme à l'API MTN
        return {
            'success': True,
            'statusCode': transaction['statusCode'],
            'statusMessage': transaction['statusMessage'],
            'data': {
                'status': transaction['status'],
                'amount': transaction['amount'],
                'date': transaction['created_at'].isoformat(),
                'channel': 'USSD',
                'customer': {
                    'phoneNumber': transaction['payer']['payerId'],
                    'name': transaction['payer']['payerName']
                },
                'charges': {
                    'amount': '0',
                    'currency': 'XOF'
                }
            },
            'providerTransactionId': transaction['transactionId'],
            'simulationInfo': {
                'scenario': transaction['scenario'],
                'elapsedSeconds': int(elapsed_time),
                'targetDelaySeconds': scenario_config['delay_seconds']
            }
        }
    
    def simulate_sms_send(self, numero_telephone: str, message: str) -> Dict[str, Any]:
        """
        Simule l'envoi d'un SMS.
        
        Args:
            numero_telephone: Numéro du destinataire
            message: Message à envoyer
            
        Returns:
            Réponse simulée d'envoi SMS
        """
        if not self.simulation_enabled:
            raise ValueError("Simulation non activée")
        
        # Simuler délai réseau
        time.sleep(self.response_delay)
        
        # Générer une réponse conforme
        message_id = f'SMS_SIM_{uuid.uuid4().hex[:8]}'
        
        return {
            'success': True,
            'messageId': message_id,
            'status': 'sent',
            'outboundSMSMessageResponse': {
                'resourceURL': f'/v3/sms/messages/{message_id}',
                'clientCorrelator': str(uuid.uuid4())
            },
            'simulationInfo': {
                'recipient': numero_telephone,
                'messageLength': len(message),
                'timestamp': timezone.now().isoformat()
            }
        }
    
    def simulate_withdrawal_request(self, withdrawal_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simule une demande de retrait MTN.
        """
        correlation_id = withdrawal_request.get('correlatorId', f'WD_{timezone.now().strftime("%Y%m%d_%H%M%S")}')
        transaction_id = f'MTN_WD_SIM_{str(uuid.uuid4())[:8]}'
        
        # Simulation d'un retrait réussi par défaut
        response_data = {
            'transactionId': transaction_id,
            'correlatorId': correlation_id,
            'status': 'SUCCESSFUL',
            'statusCode': '0000',
            'statusMessage': 'Withdrawal completed successfully',
            'amount': withdrawal_request.get('amount'),
            'currency': withdrawal_request.get('units', 'XOF'),
            'recipient': withdrawal_request.get('customerId'),
            'externalReference': withdrawal_request.get('externalReference'),
            'simulationInfo': {
                'scenario': 'withdrawal_success',
                'timestamp': timezone.now().isoformat(),
                'description': 'Simulated withdrawal for testing'
            }
        }
        
        # Stocker la transaction simulée
        self.fake_transactions[correlation_id] = {
            'type': 'withdrawal',
            'transaction_id': transaction_id,
            'status': 'SUCCESSFUL',
            'statusCode': '0000',
            'statusMessage': 'Withdrawal completed successfully',
            'amount': withdrawal_request.get('amount'),
            'currency': withdrawal_request.get('units', 'XOF'),
            'recipient': withdrawal_request.get('customerId'),
            'created_at': timezone.now(),
            'request_data': withdrawal_request,
            'response_data': response_data
        }
        
        return response_data
    
    def _get_status_message(self, status: str) -> str:
        """Retourne un message approprié pour un statut donné."""
        messages = {
            'PENDING': 'Payment is being processed',
            'SUCCESSFUL': 'Payment completed successfully',
            'FAILED': 'Payment failed',
            'APPROVED': 'Payment approved',
            'DECLINED': 'Payment declined',
            'TIMEOUT': 'Payment timeout'
        }
        return messages.get(status, f'Payment status: {status}')
    
    def _schedule_status_change(self, payment_reference: str, scenario_config: Dict):
        """
        Programme un changement de statut différé.
        En production, ceci serait géré par des tâches asynchrones (Celery).
        """
        # Pour la simulation, on se contente de stocker l'info
        # Le changement sera effectué lors de la prochaine vérification
        pass
    
    def create_test_scenarios(self) -> Dict[str, str]:
        """
        Crée des références de test pour différents scénarios.
        
        Returns:
            Dict avec les références créées pour chaque scénario
        """
        if not self.simulation_enabled:
            raise ValueError("Simulation non activée")
        
        scenarios = {}
        
        for scenario_name, scenario_config in self.test_scenarios.items():
            # Créer une requête de paiement fictive
            payment_request = {
                'countryCode': 'BJ',
                'totalAmount': {'value': '1000', 'currency': 'XOF'},
                'payer': {
                    'payerId': '22996123456',
                    'payerName': f'Test {scenario_name}',
                    'payerRef': f'TEST_{scenario_name.upper()}',
                    'payerAccountType': 'MOBILE_MONEY'
                },
                'payee': [{
                    'amount': {'value': '1000', 'currency': 'XOF'},
                    'payeeName': 'TONTIFLEX',
                    'payeeRef': f'TONTIFLEX_{scenario_name.upper()}'
                }],
                'paymentMethod': 'DigitalWallet',
                'paymentReference': f'TEST_{scenario_name.upper()}_{int(time.time())}'
            }
            
            # Simuler la création
            result = self.simulate_payment_request(payment_request, scenario_name)
            scenarios[scenario_name] = result['paymentReference']
        
        return scenarios
    
    def get_simulation_report(self) -> Dict[str, Any]:
        """
        Génère un rapport sur les transactions simulées.
        
        Returns:
            Rapport détaillé des simulations
        """
        if not self.simulation_enabled:
            return {'error': 'Simulation non activée'}
        
        total_transactions = len(self.fake_transactions)
        status_counts = {}
        scenarios_used = {}
        
        for ref, transaction in self.fake_transactions.items():
            status = transaction['status']
            scenario = transaction['scenario']
            
            status_counts[status] = status_counts.get(status, 0) + 1
            scenarios_used[scenario] = scenarios_used.get(scenario, 0) + 1
        
        return {
            'simulation_enabled': self.simulation_enabled,
            'total_transactions': total_transactions,
            'status_distribution': status_counts,
            'scenarios_used': scenarios_used,
            'available_scenarios': list(self.test_scenarios.keys()),
            'transactions': [
                {
                    'reference': ref,
                    'status': trans['status'],
                    'scenario': trans['scenario'],
                    'created_at': trans['created_at'].isoformat(),
                    'amount': trans['amount']['value']
                }
                for ref, trans in self.fake_transactions.items()
            ]
        }
    
    def reset_simulations(self):
        """Réinitialise toutes les simulations."""
        if not self.simulation_enabled:
            raise ValueError("Simulation non activée")
        
        self.fake_transactions.clear()
        cache.clear()  # Nettoyer le cache Django aussi
        
        return {
            'message': 'Simulations réinitialisées',
            'timestamp': timezone.now().isoformat()
        }


# Décorateur pour utiliser la simulation en mode DEBUG
def use_simulation_if_debug(func):
    """
    Décorateur pour utiliser automatiquement la simulation en mode DEBUG.
    """
    def wrapper(*args, **kwargs):
        if settings.DEBUG and getattr(settings, 'MTN_USE_SIMULATION', True):
            # Utiliser le service de simulation
            simulation_service = MTNSimulationService()
            return simulation_service
        else:
            # Utiliser le vrai service
            return func(*args, **kwargs)
    return wrapper


# Service hybride qui utilise simulation ou vrai service selon config
class MTNHybridService:
    """
    Service hybride qui utilise la simulation en développement
    et le vrai service MTN en production.
    """
    
    def __init__(self):
        self.use_simulation = getattr(settings, 'MTN_USE_SIMULATION', settings.DEBUG)
        
        if self.use_simulation:
            self.service = MTNSimulationService()
        else:
            from .services_mtn_new_api_complete import MTNConformeAPIService
            self.service = MTNConformeAPIService()
    
    def initier_paiement(self, *args, **kwargs):
        """Initie un paiement (simulé ou réel selon la config)."""
        if self.use_simulation:
            # Transformer les arguments en requête de paiement
            # et utiliser la simulation
            pass  # À implémenter selon vos besoins
        else:
            return self.service.initier_paiement_conforme(*args, **kwargs)
    
    def verifier_statut(self, payment_reference: str):
        """Vérifie le statut (simulé ou réel selon la config)."""
        if self.use_simulation:
            return self.service.simulate_status_check(payment_reference)
        else:
            return self.service.verifier_statut_paiement(payment_reference)
