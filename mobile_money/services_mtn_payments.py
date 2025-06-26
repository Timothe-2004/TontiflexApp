"""
TEMPORAIREMENT DÉSACTIVÉ - MIGRATION VERS KKIAPAY
Ce module sera supprimé une fois la migration KKiaPay terminée.

Nouveau module payments/ avec KKiaPay intégré.
Documentation : https://kkiapay.me/kkiapay-integration/?lang=en
Dashboard : https://app.kkiapay.me/dashboard

Mode SANDBOX activé pour tests et validation.
Changement vers LIVE après validation complète.

VOIR PROJET_HISTORIQUE.md pour suivi détaillé de la migration.
"""

import os
import requests
import base64
import logging
from django.conf import settings
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MTNOAuth2Client:
    def __init__(self):
        self.client_id = os.getenv('MTN_CONSUMER_KEY', getattr(settings, 'MTN_CONSUMER_KEY', ''))
        self.client_secret = os.getenv('MTN_CONSUMER_SECRET', getattr(settings, 'MTN_CONSUMER_SECRET', ''))
        self.subscription_key = os.getenv('MTN_SUBSCRIPTION_KEY', getattr(settings, 'MTN_SUBSCRIPTION_KEY', ''))
        self.token_url = os.getenv('MTN_OAUTH_TOKEN_URL', 'https://api.mtn.com/v1/oauth/access_token')
        self.base_url = os.getenv('MTN_API_BASE_URL', 'https://api.mtn.com/v1')
        self.access_token = None
        self.token_expiry = None

    def get_access_token(self):
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token

        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        if self.subscription_key:
            headers["Ocp-Apim-Subscription-Key"] = self.subscription_key

        data = {"grant_type": "client_credentials"}
        resp = requests.post(self.token_url, headers=headers, data=data)
        if resp.status_code == 200:
            token_data = resp.json()
            self.access_token = token_data["access_token"]
            expires_in = int(token_data.get("expires_in", 3600))
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)
            return self.access_token
        else:
            logger.error(f"OAuth2 error: {resp.status_code} {resp.text}")
            raise Exception(f"OAuth2 error: {resp.status_code} {resp.text}")

    def get_headers(self, extra_headers=None):
        token = self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        if self.subscription_key:
            headers["Ocp-Apim-Subscription-Key"] = self.subscription_key
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def post(self, endpoint, body, extra_headers=None):
        url = f"{self.base_url}{endpoint}"
        headers = self.get_headers(extra_headers)
        resp = requests.post(url, headers=headers, json=body)
        logger.info(f"POST {url} {resp.status_code} {resp.text}")
        if resp.status_code in (200, 201, 202):
            return resp.json()
        else:
            raise Exception(f"MTN API error: {resp.status_code} {resp.text}")

    def get(self, endpoint, params=None, extra_headers=None):
        url = f"{self.base_url}{endpoint}"
        headers = self.get_headers(extra_headers)
        resp = requests.get(url, headers=headers, params=params)
        logger.info(f"GET {url} {resp.status_code} {resp.text}")
        if resp.status_code == 200:
            return resp.json()
        else:
            raise Exception(f"MTN API error: {resp.status_code} {resp.text}")

# Exemple d'utilisation pour générer un lien de paiement
def generer_lien_paiement(numero, montant, reference, description):
    client = MTNOAuth2Client()
    body = {
        "channel": "TONTIFLEX",
        "quoteId": reference,
        "description": description,
        "authenticationType": "Query Payment",
        "deliveryMethod": "Paylink",
        "payer": {
            "payerIdType": "MSISDN",
            "payerId": numero,
            "payerName": f"Client {numero[-4:]}"
        },
        "totalAmount": {
            "amount": float(montant),
            "units": "XOF"
        },
        "itemDetails": [
            {
                "name": "Adhésion Tontine",
                "description": description
            }
        ]
    }
    return client.post("/payments/payment-link", body)

# Exemple d'utilisation pour vérifier le statut d'un paiement
def verifier_statut_paiement(correlator_id):
    client = MTNOAuth2Client()
    return client.get(f"/payments/{correlator_id}/transactionStatus")

# Exemple d'utilisation pour initier un retrait
def initier_retrait(body):
    client = MTNOAuth2Client()
    return client.post("/withdrawals", body)
