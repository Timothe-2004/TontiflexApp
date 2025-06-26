"""
Test de validation basique du module savings.
Ces tests vérifient que les endpoints principaux sont bien configurés.
"""

import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import Client, SFD

User = get_user_model()


class SavingsBasicTest(TestCase):
    """Tests de base pour vérifier la configuration du module savings"""
    
    def setUp(self):
        """Préparation des données de test"""
        self.client_api = APIClient()
        
        # Créer une SFD de test
        self.sfd = SFD.objects.create(
            nom="SFD Test",
            adresse="Cotonou",
            telephone="+22970000001",
            email="test@sfd.bj"
        )
        
        # Créer un utilisateur client
        self.user_client = User.objects.create_user(
            username="client_test",
            email="client@test.com", 
            password="testpass123"
        )
        
        # Créer le profil client
        self.client_profile = Client.objects.create(
            user=self.user_client,
            nom="Client",
            prenom="Test",
            telephone="+22970000002"
            # Note: Client n'a pas de SFD direct - l'association se fait via l'agent validateur
        )
    
    def test_savings_endpoints_accessible(self):
        """Test que les endpoints savings sont accessibles"""
        # Test GET liste des comptes (sans authentification)
        response = self.client_api.get('/api/savings/accounts/')
        # Devrait retourner 401 (non authentifié) et non 404 (endpoint introuvable)
        self.assertIn(response.status_code, [401, 403])
        
        # Test GET liste des transactions
        response = self.client_api.get('/api/savings/transactions/')
        self.assertIn(response.status_code, [401, 403])
    
    def test_models_import_correctly(self):
        """Test que les modèles s'importent correctement"""
        from savings.models import SavingsAccount, SavingsTransaction
        
        # Test des choix de statut
        self.assertIn('en_cours_creation', SavingsAccount.StatutChoices.values)
        self.assertIn('actif', SavingsAccount.StatutChoices.values)
        
        # Test des choix d'opérateur
        self.assertIn('mtn', SavingsAccount.OperateurChoices.values)
        self.assertIn('moov', SavingsAccount.OperateurChoices.values)
    
    def test_serializers_import_correctly(self):
        """Test que les serializers s'importent correctement"""
        from savings.serializers import (
            SavingsAccountSerializer, 
            SavingsTransactionSerializer,
            CreateRequestSerializer,
            ValidateRequestSerializer
        )
        
        # Les serializers doivent exister
        self.assertTrue(SavingsAccountSerializer)
        self.assertTrue(SavingsTransactionSerializer)
        self.assertTrue(CreateRequestSerializer)
        self.assertTrue(ValidateRequestSerializer)
    
    def test_permissions_import_correctly(self):
        """Test que les permissions s'importent correctement"""
        from savings.permissions import (
            SavingsAccountPermission,
            SavingsTransactionPermission,
            IsSavingsAccountClient
        )
        
        # Les permissions doivent exister
        self.assertTrue(SavingsAccountPermission)
        self.assertTrue(SavingsTransactionPermission)
        self.assertTrue(IsSavingsAccountClient)
    
    def test_utils_import_correctly(self):
        """Test que les utils s'importent correctement"""
        from savings.utils import (
            valider_eligibilite_compte_epargne,
            valider_montant_transaction,
            calculer_statistiques_compte
        )
        
        # Les fonctions utils doivent exister
        self.assertTrue(valider_eligibilite_compte_epargne)
        self.assertTrue(valider_montant_transaction)
        self.assertTrue(calculer_statistiques_compte)
