import os
import requests
import json
from urllib.parse import urlencode
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()


# Récupérer les credentials MTN
def get_env(key, default=None):
    return os.getenv(key, default)

# Paiements (Payments V1 - prod)
MTN_API_BASE_URL = 'https://api.mtn.com/v1'
MTN_OAUTH_TOKEN_URL = 'https://api.mtn.com/v1/oauth/access_token'
MTN_SUBSCRIPTION_KEY = 'lG9GXNbqSE6RDA2XbzkZ1P5T7nv14ZiP'

# Retraits (Withdrawals V1 - sandbox/preprod)
MTN_WITHDRAWALS_API_BASE_URL = 'https://preprod.mtn.com/v1/'
MTN_WITHDRAWALS_OAUTH_TOKEN_URL = ' https://mtn-preprod-preprod.apigee.net/v1/oauth/access_token'
MTN_WITHDRAWALS_API_KEY = 'lG9GXNbqSE6RDA2XbzkZ1P5T7nv14ZiP'

# Commun
MTN_CONSUMER_KEY = 'lG9GXNbqSE6RDA2XbzkZ1P5T7nv14ZiP'
MTN_CONSUMER_SECRET = '1rV8WBe78VTnaRzR'

# 1. Obtenir un access_token OAuth2 pour Payments (prod)
def get_payments_access_token():
    print("[DEBUG] MTN_SUBSCRIPTION_KEY:", MTN_SUBSCRIPTION_KEY)
    print("[DEBUG] MTN_CONSUMER_KEY:", MTN_CONSUMER_KEY)
    print("[DEBUG] MTN_CONSUMER_SECRET:", MTN_CONSUMER_SECRET)
    headers = {
        'Ocp-Apim-Subscription-Key': MTN_SUBSCRIPTION_KEY,
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    params = {
        'grant_type': 'client_credentials',
    }
    data = {
        'client_id': MTN_CONSUMER_KEY,
        'client_secret': MTN_CONSUMER_SECRET,
    }
    resp = requests.post(MTN_OAUTH_TOKEN_URL, headers=headers, params=params, data=urlencode(data))
    if resp.status_code == 200:
        return resp.json()['access_token']
    print('Erreur OAuth2 Payments:', resp.status_code, resp.text)
    return None

# 1b. Obtenir un access_token OAuth2 pour Withdrawals (sandbox)
def get_withdrawals_access_token():
    print("[DEBUG] MTN_WITHDRAWALS_API_KEY:", MTN_WITHDRAWALS_API_KEY)
    print("[DEBUG] MTN_CONSUMER_KEY:", MTN_CONSUMER_KEY)
    print("[DEBUG] MTN_CONSUMER_SECRET:", MTN_CONSUMER_SECRET)
    headers = {
        'X-API-Key': MTN_WITHDRAWALS_API_KEY,
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    data = {
        'grant_type': 'client_credentials',
        'client_id': MTN_CONSUMER_KEY,
        'client_secret': MTN_CONSUMER_SECRET,
    }
    resp = requests.post(MTN_WITHDRAWALS_OAUTH_TOKEN_URL, headers=headers, data=urlencode(data))
    if resp.status_code == 200:
        return resp.json()['access_token']
    print('Erreur OAuth2 Withdrawals:', resp.status_code, resp.text)
    return None

# 2. Effectuer un paiement (Payments V1 - prod)
def make_payment(access_token, msisdn, amount, reference):
    url = f"{MTN_API_BASE_URL}/payments"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Ocp-Apim-Subscription-Key': MTN_SUBSCRIPTION_KEY,
        'Content-Type': 'application/json',
    }
    body = {
        "channel": "TONTIFLEX",
        "quoteId": reference,
        "description": "Paiement test sandbox TontiFlex",
        "authenticationType": "Query Payment",
        "deliveryMethod": "Paylink",
        "payer": {
            "payerIdType": "MSISDN",
            "payerId": msisdn,
            "payerName": f"Client {msisdn[-4:]}"
        },
        "totalAmount": {
            "amount": float(amount),
            "units": "XOF"
        },
        "itemDetails": [
            {
                "name": "Adhésion Tontine",
                "description": "Paiement sandbox"
            }
        ]
    }
    resp = requests.post(url, headers=headers, json=body)
    print("\n--- Paiement (Payments V1) ---")
    print("Status:", resp.status_code)
    print("Response:", resp.text)
    return resp.json() if resp.status_code in (200, 201) else None

# 3. Effectuer un retrait (Withdrawals V1 - sandbox)
def make_withdrawal(access_token, correlator_id, customer_id, amount):
    url = f"{MTN_WITHDRAWALS_API_BASE_URL}/withdraw"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'X-API-Key': MTN_WITHDRAWALS_API_KEY,
        'Content-Type': 'application/json',
    }
    body = {
        "correlatorId": correlator_id,
        "customerId": customer_id,
        "resource": "MSISDN",
        "amount": float(amount),
        "units": "XOF",
        "description": "Retrait test sandbox TontiFlex",
        "callingSystem": "ECW",
        "targetSystem": "ECW",
        "status": "Pending",
        "additionalInformation": [
            {"name": "test", "description": "Retrait sandbox"}
        ]
    }
    resp = requests.post(url, headers=headers, json=body)
    print("\n--- Retrait (Withdrawals V1) ---")
    print("Status:", resp.status_code)
    print("Response:", resp.text)
    return resp.json() if resp.status_code in (200, 201) else None

if __name__ == "__main__":
    # Exemple de MSISDN sandbox (doit être un numéro de test accepté par MTN sandbox)
    msisdn = "22990000001"  # Numéro de test sandbox
    amount = 1000
    reference = "TONTIFLEX_TEST_001"
    correlator_id = "TONTIFLEX_CORR_001"
    customer_id = msisdn

    # Paiement (Payments V1 - prod)
    print("Obtention du token OAuth2 pour Payments...")
    payments_access_token = get_payments_access_token()
    if not payments_access_token:
        print("Impossible d'obtenir un access_token Payments. Vérifiez vos credentials.")
    else:
        payment_result = make_payment(payments_access_token, msisdn, amount, reference)

    # Retrait (Withdrawals V1 - sandbox)
    print("Obtention du token OAuth2 pour Withdrawals...")
    withdrawals_access_token = get_withdrawals_access_token()
    if not withdrawals_access_token:
        print("Impossible d'obtenir un access_token Withdrawals. Vérifiez vos credentials.")
        withdrawal_result = None
    else:
        withdrawal_result = make_withdrawal(withdrawals_access_token, correlator_id, customer_id, amount)

    print("\n--- Résumé ---")
    print("Paiement:", json.dumps(payment_result if 'payment_result' in locals() else None, indent=2, ensure_ascii=False))
    print("Retrait:", json.dumps(withdrawal_result, indent=2, ensure_ascii=False))
