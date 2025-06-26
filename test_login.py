#!/usr/bin/env python3
"""
Script de test pour l'endpoint /auth/login/
"""
import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"
LOGIN_ENDPOINT = f"{BASE_URL}/auth/login/"

def test_login_endpoint():
    """Test les différents formats de requête pour identifier le problème"""
    
    print("🧪 Test de l'endpoint /auth/login/")
    print("=" * 50)
    
    # Test 1: Requête vide (reproduire l'erreur)
    print("\n1. Test requête vide:")
    try:
        response = requests.post(LOGIN_ENDPOINT, json={})
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   Erreur: {e}")
    
    # Test 2: Données manquantes
    print("\n2. Test données partielles:")
    try:
        response = requests.post(LOGIN_ENDPOINT, json={"username": "test"})
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   Erreur: {e}")
    
    # Test 3: Format JWT standard (username/password)
    print("\n3. Test format JWT standard:")
    try:
        response = requests.post(LOGIN_ENDPOINT, json={
            "username": "admin",
            "password": "password123"
        })
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   Erreur: {e}")
    
    # Test 4: Format email/motDePasse (selon le serializer)
    print("\n4. Test format email/motDePasse:")
    try:
        response = requests.post(LOGIN_ENDPOINT, json={
            "email": "admin@example.com",
            "motDePasse": "password123"
        })
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   Erreur: {e}")
    
    # Test 5: Endpoint info
    print("\n5. Test OPTIONS pour voir les champs requis:")
    try:
        response = requests.options(LOGIN_ENDPOINT)
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
    except Exception as e:
        print(f"   Erreur: {e}")

if __name__ == "__main__":
    test_login_endpoint()
