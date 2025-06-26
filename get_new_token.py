#!/usr/bin/env python3
"""
Script pour obtenir un nouveau token JWT
"""
import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"
LOGIN_ENDPOINT = f"{BASE_URL}/auth/login/"

def get_new_token():
    """Obtient un nouveau token JWT"""
    print("🔐 Obtention d'un nouveau token JWT...")
    print("=" * 50)
    
    try:
        response = requests.post(LOGIN_ENDPOINT, json={
            "email": "admin@tontiflex.bj",
            "motDePasse": "admin"
        })
        
        if response.status_code == 200:
            data = response.json()
            print("🎉 NOUVEAU TOKEN OBTENU !")
            print(f"✅ Access Token: {data.get('access', 'N/A')}")
            print(f"✅ Refresh Token: {data.get('refresh', 'N/A')}")
            print(f"✅ User Info: {data.get('user', 'N/A')}")
            
            # Test avec le nouveau token
            test_with_new_token(data.get('access'))
            
        else:
            print(f"❌ Erreur de connexion: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"Erreur: {e}")

def test_with_new_token(access_token):
    """Test d'un endpoint avec le nouveau token"""
    print("\n🧪 Test avec le nouveau token...")
    
    try:
        # Test un endpoint administratif
        admin_endpoint = f"{BASE_URL}/api/administrateurs-sfd/"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(admin_endpoint, headers=headers)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Endpoint administratif accessible !")
            data = response.json()
            print(f"Nombre d'admins SFD: {data.get('count', 0)}")
        else:
            print(f"❌ Problème d'accès: {response.text}")
            
    except Exception as e:
        print(f"Erreur de test: {e}")

if __name__ == "__main__":
    get_new_token()
