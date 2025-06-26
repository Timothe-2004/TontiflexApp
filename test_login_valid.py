#!/usr/bin/env python3
"""
Test de connexion avec un utilisateur valide
"""
import requests
import json

# Test avec un utilisateur réel
LOGIN_ENDPOINT = "http://localhost:8000/auth/login/"

print("🧪 Test de connexion avec utilisateur valide")
print("=" * 50)

try:
    response = requests.post(LOGIN_ENDPOINT, json={
        "email": "test@example.com",
        "motDePasse": "testpass123"
    })
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        data = response.json()
        print("🎉 CONNEXION RÉUSSIE !")
        print(f"✅ Access Token: {data.get('access', 'N/A')[:50]}...")
        print(f"✅ Refresh Token: {data.get('refresh', 'N/A')[:50]}...")
        print(f"✅ User Info: {data.get('user', 'N/A')}")
    else:
        print("❌ Connexion échouée")
        
except Exception as e:
    print(f"Erreur: {e}")
