"""
Service pour les retraits Mobile Money via MTN Withdrawals V1 (conforme withdrawals-v1.yaml).
Utilise l'API officielle MTN : https://api.mtn.com/v1/withdrawals
"""
import os
import requests
import logging
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)

class MTNWithdrawalsV1Service:
    def __init__(self):
        # Configuration conforme au Swagger withdrawals-v1.yaml  
        self.base_url = os.getenv('MTN_WITHDRAWALS_API_BASE_URL', 'https://api.mtn.com/v1/withdrawals')
        self.api_key = os.getenv('MTN_WITHDRAWALS_API_KEY')
        self.client_id = os.getenv('MTN_WITHDRAWALS_CLIENT_ID')
        self.client_secret = os.getenv('MTN_WITHDRAWALS_CLIENT_SECRET')
        self.subscription_key = os.getenv('MTN_WITHDRAWALS_SUBSCRIPTION_KEY')
        self.callback_url = os.getenv('MTN_WITHDRAWALS_CALLBACK_URL')

    def _get_access_token(self) -> str:
        """Obtient un token d'accès conforme à l'API MTN Withdrawals V1."""
        url = 'https://api.mtn.com/v1/oauth/access_token'
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        response = requests.post(url, headers=headers, data=data, timeout=30)
        if response.status_code == 200:
            return response.json().get('access_token')
        logger.error(f"Erreur obtention token Withdrawals V1: {response.status_code} - {response.text}")
        raise Exception('Erreur authentification Withdrawals V1')

    def create_withdrawal(self, correlator_id: str, customer_id: str, resource: str, amount: float, units: str = 'XOF', description: str = '', external_reference: str = None, calling_system: str = 'ECW', target_system: str = 'ECW', status: str = 'Pending', additional_information: list = None) -> Dict:
        """
        Crée une demande de retrait via l'API Withdrawals V1.
        """
        access_token = self._get_access_token()
        url = f"{self.base_url}/withdraw"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json',
        }
        payload = {
            'correlatorId': correlator_id,
            'customerId': customer_id,
            'resource': resource,
            'transactionRequestDate': datetime.utcnow().isoformat() + 'Z',
            'callingSystem': calling_system,
            'targetSystem': target_system,
            'description': description,
            'amount': {
                'amount': amount,
                'units': units,
            },
            'status': status,
            'externalReference': external_reference or correlator_id,
        }
        if additional_information:
            payload['additionalInformation'] = additional_information
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code in [200, 201, 202]:
            return response.json()
        logger.error(f"Erreur création retrait Withdrawals V1: {response.status_code} - {response.text}")
        raise Exception('Erreur création retrait Withdrawals V1')
