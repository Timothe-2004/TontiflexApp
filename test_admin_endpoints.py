#!/usr/bin/env python3
"""
Test avec un utilisateur superuser
"""
import requests
import json

# Test avec le superuser
LOGIN_ENDPOINT = "http://localhost:8000/auth/login/"
ADMIN_ENDPOINT = "http://localhost:8000/admin/administrateurs-sfd/"

print("🧪 Test connexion superuser + endpoint admin")
print("=" * 60)

# 1. Se connecter avec le superuser
print("\n1. Connexion superuser...")
response = requests.post(LOGIN_ENDPOINT, json={
    "email": "test@example.com",
    "motDePasse": "testpass123"
})

if response.status_code == 200:
    data = response.json()
    access_token = data['access']
    print(f"✅ Token obtenu: {access_token[:50]}...")
    
    # 2. Tester l'endpoint admin
    print("\n2. Test endpoint administrateurs SFD...")
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    admin_response = requests.get(ADMIN_ENDPOINT, headers=headers)
    print(f"Status: {admin_response.status_code}")
    print(f"Content-Type: {admin_response.headers.get('content-type', 'Unknown')}")
    
    if admin_response.status_code == 200:
        if 'application/json' in admin_response.headers.get('content-type', ''):
            print("✅ Réponse JSON reçue !")
            try:
                json_data = admin_response.json()
                print(f"✅ Données: {json.dumps(json_data, indent=2)[:200]}...")
            except:
                print("❌ Erreur parsing JSON")
        else:
            print("❌ Réponse HTML reçue au lieu de JSON")
            print(f"HTML snippet: {admin_response.text[:200]}...")
    else:
        print(f"❌ Erreur {admin_response.status_code}: {admin_response.text[:200]}...")
        
else:
    print(f"❌ Erreur connexion: {response.status_code} - {response.text}")
