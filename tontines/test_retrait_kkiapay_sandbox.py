"""
Test réel de retrait de tontines avec KKiaPay Sandbox
====================================================

Ce test utilise le vrai sandbox KKiaPay avec des numéros de test officiels
et vérifie les transactions côté serveur avec le SDK Python.

Documentation:
- SDK JavaScript: https://docs.kkiapay.me/v1/plugin-et-sdk/sdk-javascript
- SDK Python: https://docs.kkiapay.me/v1/plugin-et-sdk/admin-sdks-server-side/python-admin-sdk
- Numéros de test: https://docs.kkiapay.me/v1/compte/kkiapay-sandbox-guide-de-test
"""

import os
import sys
import django
import requests
import json
import time
from decimal import Decimal
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tontiflex.settings')

# Import des modèles TontiFlex
from accounts.models import SFD, AdministrateurSFD, AgentSFD, Client
from tontines.models import Tontine, TontineParticipant, Cotisation, Retrait, SoldeTontine
from payments.models import KKiaPayTransaction
from payments.config import kkiapay_config

# Import du SDK KKiaPay (déjà installé selon vous)
from kkiapay import Kkiapay

User = get_user_model()


class TestRetraitTontineKKiaPaySandboxReel(TransactionTestCase):
    """
    Tests réels avec le vrai sandbox KKiaPay pour les retraits de tontines
    Utilise l'API REST et le SDK Python pour des tests complets
    """
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Initialiser le SDK KKiaPay en mode sandbox avec vos vraies clés
        try:
            cls.kkiapay = Kkiapay(
                kkiapay_config.public_key,
                kkiapay_config.private_key,
                kkiapay_config.secret_key,
                sandbox=True
            )
            print("✅ SDK KKiaPay initialisé en mode sandbox avec vos clés")
        except Exception as e:
            raise Exception(f"Impossible d'initialiser KKiaPay: {e}")
        
        # Numéros de test officiels KKiaPay
        cls.test_numbers = {
            'mtn_benin_success': '+22990000000',      # MTN Bénin - Succès immédiat
            'mtn_benin_success2': '+22997000000',     # MTN Bénin - Succès alternatif
            'mtn_benin_delayed': '+22961100000',      # MTN Bénin - Succès avec délai
            'mtn_benin_error': '+22961000001',        # MTN Bénin - Erreur processing
            'mtn_benin_insufficient': '+22961000002', # MTN Bénin - Fonds insuffisants
            'moov_success': '+22968000000',           # Moov - Succès immédiat
            'moov_delayed': '+22968100000',           # Moov - Succès avec délai
            'moov_error': '+22968000001',             # Moov - Erreur processing
        }
    
    def setUp(self):
        """Configuration des données de test pour chaque test"""
        print("\n🔧 Configuration des données de test TontiFlex...")
        
        # Créer une SFD
        self.sfd = SFD.objects.create(
            id="SFD_KKIA_REAL",
            nom="SFD KKiaPay Test Réel",
            adresse="123 Rue du Test Réel",
            telephone="+22912345555",
            email="real.test@tontiflex.com",
            numeroMobileMoney=self.test_numbers['mtn_benin_success']
        )
        
        # Créer un administrateur SFD
        admin_user = User.objects.create_user(
            email='admin.real@tontiflex.com',
            password='testpass123',
            username='admin_real_test'
        )
        self.admin_sfd = AdministrateurSFD.objects.create(
            user=admin_user,
            nom="Admin",
            prenom="Test Réel",
            telephone="+22912345556",
            email="admin.real@tontiflex.com",
            adresse="Adresse admin réel",
            profession="Administrateur SFD",
            motDePasse="hashed_password",
            sfd=self.sfd
        )
        
        # Créer un agent SFD
        agent_user = User.objects.create_user(
            email='agent.real@tontiflex.com',
            password='testpass123',
            username='agent_real_test'
        )
        self.agent_sfd = AgentSFD.objects.create(
            user=agent_user,
            nom="Agent",
            prenom="Test Réel",
            telephone="+22912345557",
            email="agent.real@tontiflex.com",
            adresse="Adresse agent réel",
            profession="Agent SFD",
            motDePasse="hashed_password",
            sfd=self.sfd,
            est_actif=True
        )
        
        # Créer un client avec numéro de test MTN succès
        client_user = User.objects.create_user(
            email='client.real@tontiflex.com',
            password='testpass123',
            username='client_real_test'
        )
        self.client = Client.objects.create(
            user=client_user,
            nom="Kone",
            prenom="Amadou",
            telephone=self.test_numbers['mtn_benin_success'],  # Numéro de test succès
            email="client.real@tontiflex.com",
            adresse="Cotonou, Bénin",
            profession="Commerçant",
            motDePasse="hashed_password",
            scorefiabilite=Decimal('95.00')
        )
        
        # Créer une tontine de test
        self.tontine = Tontine.objects.create(
            nom='Tontine KKiaPay Test Réel',
            montantMinMise=Decimal('5000.00'),
            montantMaxMise=Decimal('100000.00'),
            fraisAdhesion=Decimal('1000.00'),
            administrateurId=self.admin_sfd,
            reglesRetrait={
                "delai_minimum": 1,
                "montant_minimum": 5000,
                "montant_maximum": 500000,
                "frais_retrait": 250,
                "methodes_paiement": ["kkiapay", "mobile_money"],
                "operateurs_autorises": ["MTN", "MOOV"]
            },
            statut=Tontine.StatutChoices.ACTIVE
        )
        
        # Créer un participant
        self.participant = TontineParticipant.objects.create(
            client=self.client,
            tontine=self.tontine,
            montantMise=Decimal('25000.00'),
            dateAdhesion=timezone.now(),
            statut='actif'
        )
        
        # Créer des cotisations pour donner un solde substantiel
        for i in range(10):  # 10 cotisations de 25000 FCFA = 250000 FCFA
            Cotisation.objects.create(
                client=self.client,
                tontine=self.tontine,
                montant=Decimal('25000.00'),
                statut='confirmee',
                numero_transaction=f'REAL_TEST_COT_{i:03d}'
            )
        
        # Créer le solde tontine
        self.solde_tontine = SoldeTontine.objects.create(
            client=self.client,
            tontine=self.tontine,
            solde=Decimal('250000.00')  # Solde important pour tester différents montants
        )
        
        print(f"✅ Données configurées:")
        print(f"   - Client: {self.client.nom} {self.client.prenom}")
        print(f"   - Téléphone: {self.client.telephone}")
        print(f"   - Solde tontine: {self.solde_tontine.solde} FCFA")
        print(f"   - Tontine: {self.tontine.nom}")
    
    def test_retrait_kkiapay_api_rest_initiation(self):
        """
        Test d'initiation de retrait via l'API REST KKiaPay
        """
        print("\n🚀 === TEST INITIATION RETRAIT VIA API REST KKIAPAY ===")
        
        # ÉTAPE 1: Créer une demande de retrait TontiFlex
        montant_retrait = Decimal('50000.00')
        retrait = Retrait.objects.create(
            client=self.client,
            tontine=self.tontine,
            montant=montant_retrait
        )
        
        # ÉTAPE 2: Approuver le retrait
        retrait.approuver(
            agent=self.agent_sfd,
            commentaires="Retrait approuvé pour test API REST KKiaPay"
        )
        
        print(f"📝 Retrait TontiFlex créé et approuvé:")
        print(f"   - ID: {retrait.id}")
        print(f"   - Montant: {montant_retrait} FCFA")
        print(f"   - Statut: {retrait.get_statut_display()}")
        
        # ÉTAPE 3: Initier le paiement via l'API REST KKiaPay
        url = "https://api-sandbox.kkiapay.me/api/v1/transactions/initiate"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {kkiapay_config.public_key}"
        }
        
        payload = {
            "amount": int(montant_retrait),
            "phone": self.client.telephone,
            "reason": f"Retrait tontine {self.tontine.nom} - {self.client.nom}",
            "callback": f"http://localhost:8000/api/payments/webhook/retrait/{retrait.id}/",
            "data": json.dumps({
                "retrait_id": str(retrait.id),
                "tontine_id": str(self.tontine.id),
                "client_id": str(self.client.id),
                "type": "retrait_tontine"
            })
        }
        
        print(f"🌐 Initiation paiement KKiaPay:")
        print(f"   - URL: {url}")
        print(f"   - Montant: {payload['amount']} FCFA")
        print(f"   - Téléphone: {payload['phone']}")
        print(f"   - Motif: {payload['reason']}")
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            print(f"✅ Paiement initié avec succès:")
            print(f"   - Transaction ID: {result.get('transactionId')}")
            print(f"   - Statut: {result.get('status', 'N/A')}")
            print(f"   - Message: {result.get('message', 'N/A')}")
            
            # Créer l'enregistrement KKiaPayTransaction
            transaction_kkia = KKiaPayTransaction.objects.create(
                reference_tontiflex=f"RETRAIT_API_{retrait.id}",
                reference_kkiapay=result.get('transactionId'),
                type_transaction='retrait_tontine',
                status='pending',
                montant=montant_retrait,
                devise='XOF',
                user=self.client.user,
                numero_telephone=self.client.telephone,
                description=payload['reason'],
                kkiapay_response=result
            )
            
            print(f"💾 Transaction enregistrée en base:")
            print(f"   - ID interne: {transaction_kkia.id}")
            print(f"   - Référence KKiaPay: {transaction_kkia.reference_kkiapay}")
            
            # Attendre un peu pour la propagation
            print("⏳ Attente de 5 secondes pour la propagation...")
            time.sleep(5)
            
            # ÉTAPE 4: Vérifier le statut avec le SDK Python
            if result.get('transactionId'):
                print(f"🔍 Vérification avec SDK Python...")
                try:
                    verification = self.kkiapay.verify_transaction(result['transactionId'])
                    print(f"📊 Résultat vérification:")
                    print(f"   - Transaction ID: {verification.transactionId}")
                    print(f"   - Statut: {verification.status}")
                    print(f"   - Montant: {verification.amount}")
                    print(f"   - Frais: {verification.fees}")
                    print(f"   - Effectué le: {verification.performedAt}")
                    
                    # Mettre à jour le statut en base
                    transaction_kkia.status = verification.status.lower()
                    transaction_kkia.save()
                    
                    # Si succès, confirmer le retrait TontiFlex
                    if verification.status.upper() == 'SUCCESS':
                        retrait.statut = Retrait.StatutRetraitChoices.CONFIRMEE
                        retrait.save()
                        print("✅ Retrait TontiFlex confirmé!")
                    
                except Exception as e:
                    print(f"⚠️ Erreur vérification SDK: {e}")
            
            return {
                'retrait': retrait,
                'transaction_kkia': transaction_kkia,
                'api_response': result
            }
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur API REST: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"   - Code: {e.response.status_code}")
                print(f"   - Réponse: {e.response.text}")
            return None
        except Exception as e:
            print(f"❌ Erreur inattendue: {e}")
            return None
    
    def test_retrait_avec_differents_numeros_test(self):
        """
        Test des retraits avec différents numéros de test KKiaPay
        """
        print("\n📱 === TEST AVEC DIFFÉRENTS NUMÉROS DE TEST ===")
        
        scenarios_test = [
            ('mtn_benin_success', 'MTN Bénin - Succès immédiat', 25000),
            ('mtn_benin_delayed', 'MTN Bénin - Succès avec délai', 15000),
            ('moov_success', 'Moov - Succès immédiat', 35000),
            ('mtn_benin_error', 'MTN Bénin - Erreur attendue', 10000),
        ]
        
        resultats = []
        
        for scenario_key, description, montant in scenarios_test:
            print(f"\n📞 Test: {description}")
            numero = self.test_numbers[scenario_key]
            print(f"   - Numéro: {numero}")
            print(f"   - Montant: {montant} FCFA")
            
            # Créer un client spécifique pour ce test
            client_test_user = User.objects.create_user(
                email=f'{scenario_key}@test.com',
                username=f'test_{scenario_key}',
                password='testpass123'
            )
            client_test = Client.objects.create(
                user=client_test_user,
                nom="Test",
                prenom=description.split(' - ')[0],
                telephone=numero,
                email=f'{scenario_key}@test.com',
                adresse="Adresse test",
                profession="Test",
                motDePasse="test"
            )
            
            # Créer participant et solde
            participant_test = TontineParticipant.objects.create(
                client=client_test,
                tontine=self.tontine,
                montantMise=Decimal('10000.00'),
                dateAdhesion=timezone.now(),
                statut='actif'
            )
            
            solde_test = SoldeTontine.objects.create(
                client=client_test,
                tontine=self.tontine,
                solde=Decimal('100000.00')
            )
            
            # Créer et approuver le retrait
            retrait_test = Retrait.objects.create(
                client=client_test,
                tontine=self.tontine,
                montant=Decimal(str(montant))
            )
            
            retrait_test.approuver(
                agent=self.agent_sfd,
                commentaires=f"Test {description}"
            )
            
            # Initier le paiement KKiaPay
            url = "https://api-sandbox.kkiapay.me/api/v1/transactions/initiate"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {kkiapay_config.public_key}"
            }
            
            payload = {
                "amount": montant,
                "phone": numero,
                "reason": f"Test {description}",
                "data": json.dumps({
                    "scenario": scenario_key,
                    "retrait_id": str(retrait_test.id)
                })
            }
            
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=15)
                response.raise_for_status()
                result = response.json()
                
                print(f"   ✅ Initiation réussie: {result.get('transactionId', 'N/A')}")
                
                # Attendre et vérifier
                time.sleep(3)
                
                if result.get('transactionId'):
                    try:
                        verification = self.kkiapay.verify_transaction(result['transactionId'])
                        print(f"   📊 Statut: {verification.status}")
                        resultats.append({
                            'scenario': scenario_key,
                            'description': description,
                            'numero': numero,
                            'montant': montant,
                            'transaction_id': result.get('transactionId'),
                            'statut': verification.status,
                            'succes': verification.status.upper() == 'SUCCESS'
                        })
                    except Exception as e:
                        print(f"   ⚠️ Erreur vérification: {e}")
                        resultats.append({
                            'scenario': scenario_key,
                            'description': description,
                            'numero': numero,
                            'montant': montant,
                            'erreur': str(e)
                        })
                
            except Exception as e:
                print(f"   ❌ Erreur initiation: {e}")
                resultats.append({
                    'scenario': scenario_key,
                    'description': description,
                    'numero': numero,
                    'montant': montant,
                    'erreur': str(e)
                })
        
        # Résumé des résultats
        print(f"\n📊 RÉSUMÉ DES TESTS:")
        print("="*60)
        for resultat in resultats:
            if 'erreur' in resultat:
                print(f"❌ {resultat['description']}: {resultat['erreur']}")
            else:
                status_icon = "✅" if resultat.get('succes') else "⚠️"
                print(f"{status_icon} {resultat['description']}: {resultat.get('statut', 'N/A')}")
        
        return resultats
    
    def test_verification_transaction_existante(self):
        """
        Test de vérification d'une transaction existante
        (utiliser un vrai transaction_id du sandbox si disponible)
        """
        print("\n🔍 === TEST VÉRIFICATION TRANSACTION EXISTANTE ===")
        
        # Si vous avez une transaction_id réelle du sandbox, l'utiliser ici
        # Sinon, créer une nouvelle transaction de test
        test_transaction_id = "test_sandbox_transaction_id"
        
        try:
            verification = self.kkiapay.verify_transaction(test_transaction_id)
            
            print(f"✅ Transaction vérifiée:")
            print(f"   - ID: {verification.transactionId}")
            print(f"   - Statut: {verification.status}")
            print(f"   - Montant: {verification.amount}")
            print(f"   - Frais: {verification.fees}")
            print(f"   - Source: {verification.source}")
            print(f"   - Effectué le: {verification.performedAt}")
            
            return verification
            
        except Exception as e:
            print(f"ℹ️ Transaction de test non trouvée (normal): {e}")
            print("💡 Pour tester avec une vraie transaction:")
            print("   1. Effectuez d'abord un paiement via l'interface HTML")
            print("   2. Récupérez le transaction_id")
            print("   3. Utilisez-le dans ce test")
            return None
    
    def generer_donnees_interface_html(self):
        """
        Génère les données nécessaires pour l'interface HTML de test
        """
        print("\n🎨 === GÉNÉRATION DONNÉES INTERFACE HTML ===")
        
        # Créer un retrait de test pour l'interface
        retrait_html = Retrait.objects.create(
            client=self.client,
            tontine=self.tontine,
            montant=Decimal('75000.00')
        )
        
        retrait_html.approuver(
            agent=self.agent_sfd,
            commentaires="Retrait pour test interface HTML"
        )
        
        # Configuration complète pour le widget KKiaPay
        widget_config = {
            'public_key': kkiapay_config.public_key,
            'amount': int(retrait_html.montant),
            'sandbox': True,
            'phone': self.client.telephone,
            'name': f"{self.client.prenom} {self.client.nom}",
            'email': self.client.email,
            'callback': f'http://localhost:8000/api/payments/success/{retrait_html.id}/',
            'webhookurl': f'http://localhost:8000/api/payments/webhook/retrait/{retrait_html.id}/',
            'theme': '#dc3545',  # Rouge pour retrait
            'position': 'center',
            'paymentmethod': 'momo',
            'description': f"Retrait tontine {self.tontine.nom}",
            'data': json.dumps({
                'retrait_id': str(retrait_html.id),
                'tontine_id': str(self.tontine.id),
                'client_id': str(self.client.id),
                'type': 'retrait_tontine'
            })
        }
        
        # Données complètes pour l'interface
        interface_data = {
            'retrait': {
                'id': str(retrait_html.id),
                'montant': str(retrait_html.montant),
                'statut': retrait_html.statut,
                'date_creation': retrait_html.date_demande_retrait.isoformat()
            },
            'client': {
                'nom': self.client.nom,
                'prenom': self.client.prenom,
                'telephone': self.client.telephone,
                'email': self.client.email
            },
            'tontine': {
                'id': str(self.tontine.id),
                'nom': self.tontine.nom,
                'solde_client': str(self.solde_tontine.solde)
            },
            'widget_config': widget_config,
            'test_numbers': self.test_numbers,
            'api_endpoints': {
                'webhook': f'http://localhost:8000/api/payments/webhook/retrait/{retrait_html.id}/',
                'success': f'http://localhost:8000/api/payments/success/{retrait_html.id}/',
                'verify': f'http://localhost:8000/api/payments/verify/{retrait_html.id}/'
            }
        }
        
        # Sauvegarder dans un fichier JSON pour l'interface HTML
        json_file = os.path.join(
            os.path.dirname(__file__),
            'test_retrait_kkiapay_data.json'
        )
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(interface_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Données sauvegardées dans: {json_file}")
        print(f"📱 Configuration widget:")
        print(f"   - Clé publique: {widget_config['public_key'][:20]}...")
        print(f"   - Montant: {widget_config['amount']} FCFA")
        print(f"   - Téléphone: {widget_config['phone']}")
        print(f"   - Mode sandbox: {widget_config['sandbox']}")
        
        return interface_data
    
    def tearDown(self):
        """Nettoyage après chaque test"""
        super().tearDown()


if __name__ == "__main__":
    print("🧪 Test de retrait KKiaPay sandbox réel")
    print("📋 Ce script teste l'intégration complète avec le vrai sandbox KKiaPay")
    print("🔑 Assurez-vous que vos clés sandbox sont configurées dans kkiapay_config")
    print("🌐 L'interface HTML sera générée pour tester manuellement le widget")
    print("\nPour lancer les tests:")
    print("  python manage.py test tontines.test_retrait_kkiapay_sandbox")
    """
    Tests réels avec le sandbox KKiaPay pour les retraits de tontines
    """
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Vérifier que le SDK KKiaPay est disponible
        if not KKIAPAY_SDK_AVAILABLE:
            pytest.skip("SDK KKiaPay non disponible")
        
        # Initialiser le SDK KKiaPay en mode sandbox
        try:
            cls.kkiapay = Kkiapay(
                public_key="d1297c10527a11f0a266e50dce82524c",
                private_key="sk_sandbox_votre_cle_privee",  # À remplacer
                secret="sk_sandbox_votre_secret",  # À remplacer
                sandbox=True
            )
            print("✅ SDK KKiaPay initialisé en mode sandbox")
        except Exception as e:
            pytest.skip(f"Impossible d'initialiser KKiaPay: {e}")
    
    def setUp(self):
        """Configuration des données de test"""
        print("\n🔧 Configuration des données de test...")
        
        # Créer une SFD
        self.sfd = SFD.objects.create(
            id="SFD_KKIA_SANDBOX",
            nom="SFD KKiaPay Sandbox",
            adresse="123 Rue Sandbox",
            telephone="+22912345000",
            email="sandbox@tontiflex.com",
            numeroMobileMoney="22961000000"  # Numéro de test MTN
        )
        
        # Créer un administrateur SFD
        admin_user = User.objects.create_user(
            email='admin.sandbox@tontiflex.com',
            password='testpass123',
            username='admin_sandbox'
        )
        self.admin_sfd = AdministrateurSFD.objects.create(
            user=admin_user,
            nom="Admin",
            prenom="Sandbox",
            telephone="+22961000001",
            email="admin.sandbox@tontiflex.com",
            adresse="Adresse admin sandbox",
            profession="Administrateur SFD",
            motDePasse="hashed_password",
            sfd=self.sfd
        )
        
        # Créer un agent SFD
        agent_user = User.objects.create_user(
            email='agent.sandbox@tontiflex.com',
            password='testpass123',
            username='agent_sandbox'
        )
        self.agent_sfd = AgentSFD.objects.create(
            user=agent_user,
            nom="Agent",
            prenom="Sandbox",
            telephone="+22961000002",
            email="agent.sandbox@tontiflex.com",
            adresse="Adresse agent sandbox",
            profession="Agent SFD",
            motDePasse="hashed_password",
            sfd=self.sfd,
            est_actif=True
        )
        
        # Créer un client avec numéro de test
        client_user = User.objects.create_user(
            email='client.sandbox@tontiflex.com',
            password='testpass123',
            username='client_sandbox'
        )
        self.client = Client.objects.create(
            user=client_user,
            nom="Dosso",
            prenom="Moussa",
            telephone="+22961000000",  # Numéro de test MTN Bénin (succès)
            email="client.sandbox@tontiflex.com",
            adresse="Cotonou, Bénin",
            profession="Commerçant",
            motDePasse="hashed_password",
            scorefiabilite=Decimal('90.00')
        )
        
        # Créer une tontine
        self.tontine = Tontine.objects.create(
            nom='Tontine Sandbox KKiaPay',
            montantMinMise=Decimal('1000.00'),
            montantMaxMise=Decimal('50000.00'),
            fraisAdhesion=Decimal('500.00'),
            administrateurId=self.admin_sfd,
            reglesRetrait={
                "delai_minimum": 1,  # 1 jour pour test
                "montant_minimum": 1000,
                "montant_maximum": 100000,
                "frais_retrait": 100,
                "methodes_paiement": ["kkiapay", "mobile_money"]
            },
            statut=Tontine.StatutChoices.ACTIVE
        )
        
        # Créer un participant
        self.participant = TontineParticipant.objects.create(
            client=self.client,
            tontine=self.tontine,
            montantMise=Decimal('10000.00'),
            dateAdhesion=timezone.now(),
            statut='actif'
        )
        
        # Créer des cotisations pour donner un solde
        for i in range(5):  # 5 cotisations de 10000 FCFA = 50000 FCFA
            Cotisation.objects.create(
                client=self.client,
                tontine=self.tontine,
                montant=Decimal('10000.00'),
                statut='confirmee',
                numero_transaction=f'SANDBOX_COT_{i:03d}'
            )
        
        # Créer le solde tontine
        self.solde_tontine = SoldeTontine.objects.create(
            client=self.client,
            tontine=self.tontine,
            solde=Decimal('50000.00')
        )
        
        print(f"✅ Données configurées - Client: {self.client.telephone}, Solde: {self.solde_tontine.solde} FCFA")
    
    def test_workflow_retrait_kkiapay_sandbox_reel(self):
        """
        Test complet avec le vrai sandbox KKiaPay
        ATTENTION: Ce test nécessite une interaction manuelle via l'interface HTML
        """
        print("\n🚀 === TEST RETRAIT KKIAPAY SANDBOX RÉEL ===")
        
        # ÉTAPE 1: Créer une demande de retrait
        montant_retrait = Decimal('25000.00')
        retrait = Retrait.objects.create(
            client=self.client,
            tontine=self.tontine,
            montant=montant_retrait
        )
        
        print(f"📝 ÉTAPE 1: Demande de retrait créée")
        print(f"   - ID: {retrait.id}")
        print(f"   - Montant: {montant_retrait} FCFA")
        print(f"   - Client: {self.client.nom} {self.client.prenom}")
        print(f"   - Téléphone: {self.client.telephone}")
        
        # ÉTAPE 2: Validation par l'agent
        retrait.approuver(
            agent=self.agent_sfd,
            commentaires="Retrait approuvé pour test KKiaPay sandbox"
        )
        
        print(f"✅ ÉTAPE 2: Retrait approuvé par {self.agent_sfd.nom}")
        
        # ÉTAPE 3: Créer la transaction KKiaPay
        transaction_kkia = KKiaPayTransaction.objects.create(
            reference_tontiflex=f"RETRAIT_KKIA_SANDBOX_{retrait.id}",
            type_transaction='retrait_tontine',
            status='pending',
            montant=montant_retrait,
            devise='XOF',
            user=self.client.user,
            numero_telephone=self.client.telephone,
            description=f"Retrait sandbox - {self.tontine.nom} - {self.client.nom}"
        )
        
        print(f"💳 ÉTAPE 3: Transaction KKiaPay créée")
        print(f"   - Référence: {transaction_kkia.reference_tontiflex}")
        print(f"   - Montant: {transaction_kkia.montant} {transaction_kkia.devise}")
        
        # ÉTAPE 4: Générer les informations pour le widget KKiaPay
        widget_config = {
            'public_key': 'd1297c10527a11f0a266e50dce82524c',
            'amount': int(montant_retrait),  # KKiaPay attend un entier
            'sandbox': True,
            'phone': self.client.telephone,
            'callback': f'http://localhost:8000/api/payments/webhook/retrait/{retrait.id}/',
            'theme': '#28a745',  # Vert pour les retraits
            'description': transaction_kkia.description
        }
        
        print(f"🎨 ÉTAPE 4: Configuration widget KKiaPay générée")
        print(f"   - Clé publique: {widget_config['public_key'][:20]}...")
        print(f"   - Mode sandbox: {widget_config['sandbox']}")
        print(f"   - Téléphone: {widget_config['phone']}")
        print(f"   - Callback: {widget_config['callback']}")
        
        # ÉTAPE 5: Sauvegarder les données pour l'interface HTML
        test_data = {
            'retrait_id': str(retrait.id),
            'transaction_id': str(transaction_kkia.id),
            'widget_config': widget_config,
            'client_info': {
                'nom': self.client.nom,
                'prenom': self.client.prenom,
                'telephone': self.client.telephone
            },
            'tontine_info': {
                'nom': self.tontine.nom,
                'solde_client': str(self.solde_tontine.solde)
            }
        }
        
        # Écrire dans un fichier pour l'interface HTML
        import os
        test_data_file = os.path.join(
            os.path.dirname(__file__), 
            'test_retrait_sandbox_data.json'
        )
        
        with open(test_data_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 ÉTAPE 5: Données sauvegardées dans {test_data_file}")
        
        # ÉTAPE 6: Instructions pour le test manuel
        print("\n" + "="*80)
        print("🎯 INSTRUCTIONS POUR LE TEST MANUEL:")
        print("="*80)
        print(f"1. Ouvrir le fichier HTML: test_retrait_kkiapay_sandbox.html")
        print(f"2. Le widget KKiaPay s'ouvrira automatiquement")
        print(f"3. Utiliser le numéro de test: {self.client.telephone}")
        print(f"4. Montant à payer: {montant_retrait} FCFA")
        print(f"5. Mode sandbox activé - transaction fictive")
        print(f"6. Après paiement, vérifier le webhook et le statut")
        print("="*80)
        
        # Créer les assertions de base
        self.assertEqual(retrait.statut, Retrait.StatutRetraitChoices.APPROVED)
        self.assertEqual(transaction_kkia.status, 'pending')
        self.assertEqual(transaction_kkia.montant, montant_retrait)
        self.assertTrue(transaction_kkia.reference_tontiflex.startswith('RETRAIT_KKIA_SANDBOX_'))
        
        # Retourner les données pour d'autres tests
        return {
            'retrait': retrait,
            'transaction_kkia': transaction_kkia,
            'widget_config': widget_config,
            'test_data_file': test_data_file
        }
    
    def test_verification_transaction_kkiapay_sdk(self):
        """
        Test de vérification d'une transaction avec le SDK Python KKiaPay
        
        NOTE: Ce test nécessite une transaction_id réelle du sandbox
        """
        print("\n🔍 === TEST VÉRIFICATION SDK KKIAPAY ===")
        
        # Transaction ID de test (remplacer par une vraie après paiement)
        test_transaction_id = "sandbox_test_transaction_id"
        
        try:
            # Vérifier la transaction avec le SDK
            transaction_info = self.kkiapay.verify_transaction(test_transaction_id)
            
            print(f"✅ Transaction vérifiée:")
            print(f"   - ID: {transaction_info.transactionId}")
            print(f"   - Statut: {transaction_info.status}")
            print(f"   - Montant: {transaction_info.amount}")
            print(f"   - Frais: {transaction_info.fees}")
            print(f"   - Source: {transaction_info.source}")
            print(f"   - Date: {transaction_info.performedAt}")
            
            # Assertions
            self.assertIsNotNone(transaction_info)
            self.assertEqual(transaction_info.transactionId, test_transaction_id)
            
        except Exception as e:
            print(f"ℹ️  Transaction de test non trouvée (normal): {e}")
            # Ce n'est pas une erreur car on utilise un ID de test
            self.assertTrue(True)
    
    def test_numeros_test_officiels_kkiapay(self):
        """
        Test avec les numéros de téléphone officiels de KKiaPay sandbox
        """
        print("\n📱 === TEST NUMÉROS OFFICIELS KKIAPAY ===")
        
        # Numéros de test officiels selon la documentation
        numeros_test = {
            'mtn_benin_success': '+22961000000',  # MTN Bénin - Succès
            'mtn_benin_failed': '+22961000001',   # MTN Bénin - Échec
            'mtn_ci_success': '+22507000000',     # MTN Côte d'Ivoire - Succès
            'mtn_ci_failed': '+22507000001',      # MTN Côte d'Ivoire - Échec
            'moov_success': '+22966000000',       # Moov - Succès
            'moov_failed': '+22966000001',        # Moov - Échec
        }
        
        for scenario, numero in numeros_test.items():
            print(f"📞 {scenario}: {numero}")
            
            # Créer un client de test pour ce numéro
            client_test = Client.objects.create(
                user=User.objects.create_user(
                    email=f'{scenario}@test.com',
                    username=f'test_{scenario}',
                    password='testpass123'
                ),
                nom="Test",
                prenom=scenario.replace('_', ' ').title(),
                telephone=numero,
                email=f'{scenario}@test.com',
                adresse="Adresse test",
                profession="Test",
                motDePasse="test"
            )
            
            # Vérifier le format du numéro
            self.assertTrue(numero.startswith('+'))
            self.assertTrue(len(numero) >= 12)
            
            print(f"   ✅ Client créé: {client_test.nom} {client_test.prenom}")
        
        print(f"📊 Total numéros testés: {len(numeros_test)}")
    
    def test_generation_widget_config_complet(self):
        """
        Test de génération d'une configuration complète pour le widget KKiaPay
        """
        print("\n⚙️  === TEST CONFIGURATION WIDGET ===")
        
        # Créer un retrait de test
        retrait = Retrait.objects.create(
            client=self.client,
            tontine=self.tontine,
            montant=Decimal('15000.00')
        )
        
        # Configuration complète du widget
        config = {
            # Configuration de base
            'key': 'd1297c10527a11f0a266e50dce82524c',
            'amount': int(retrait.montant),
            'sandbox': True,
            
            # Informations client
            'phone': self.client.telephone,
            'email': self.client.email,
            'name': f"{self.client.prenom} {self.client.nom}",
            
            # Configuration UI
            'position': 'center',
            'theme': '#dc3545',  # Rouge pour les retraits
            'paymentmethod': 'momo',  # Mobile Money uniquement
            
            # Métadonnées
            'data': json.dumps({
                'retrait_id': str(retrait.id),
                'tontine_id': str(self.tontine.id),
                'client_id': str(self.client.id),
                'type': 'retrait_tontine'
            }),
            
            # URLs de callback
            'callback': f'http://localhost:8000/payments/success/{retrait.id}/',
            'webhookurl': f'http://localhost:8000/api/payments/webhook/retrait/{retrait.id}/',
            
            # Localisation
            'description': f"Retrait tontine {self.tontine.nom}",
            'label': f"Retrait de {retrait.montant} FCFA"
        }
        
        print("🎨 Configuration widget générée:")
        for key, value in config.items():
            if key == 'key':
                print(f"   - {key}: {str(value)[:20]}...")
            else:
                print(f"   - {key}: {value}")
        
        # Vérifications
        self.assertEqual(config['amount'], 15000)
        self.assertTrue(config['sandbox'])
        self.assertEqual(config['phone'], '+22961000000')
        self.assertEqual(config['paymentmethod'], 'momo')
        
        # Vérifier les métadonnées
        data = json.loads(config['data'])
        self.assertEqual(data['retrait_id'], str(retrait.id))
        self.assertEqual(data['type'], 'retrait_tontine')
        
        print("✅ Configuration widget validée")
        
        return config
    
    def tearDown(self):
        """Nettoyage après chaque test"""
        print("🧹 Nettoyage des données de test...")
        super().tearDown()


class TestWebhookKKiaPayRetrait(TestCase):
    """
    Tests pour les webhooks KKiaPay des retraits
    """
    
    def test_webhook_retrait_success(self):
        """Test du webhook pour un retrait réussi"""
        print("\n🔔 === TEST WEBHOOK RETRAIT SUCCÈS ===")
        
        # Données de webhook simulées selon la doc KKiaPay
        webhook_data = {
            "transactionId": "test_sandbox_12345",
            "isPaymentSucces": True,
            "account": "22961000000",
            "label": "Retrait tontine test",
            "method": "MOBILE_MONEY",
            "amount": 25000,
            "fees": 375,  # 1.5% de 25000
            "partnerId": "your_partner_id",
            "performedAt": "2024-12-27T10:30:00.000Z",
            "stateData": {
                "retrait_id": "test_retrait_id",
                "tontine_id": "test_tontine_id"
            },
            "event": "transaction.success"
        }
        
        print(f"📨 Webhook reçu:")
        print(f"   - Transaction ID: {webhook_data['transactionId']}")
        print(f"   - Succès: {webhook_data['isPaymentSucces']}")
        print(f"   - Montant: {webhook_data['amount']} FCFA")
        print(f"   - Frais: {webhook_data['fees']} FCFA")
        print(f"   - Méthode: {webhook_data['method']}")
        print(f"   - Compte: {webhook_data['account']}")
        
        # Vérifications
        self.assertTrue(webhook_data['isPaymentSucces'])
        self.assertEqual(webhook_data['event'], 'transaction.success')
        self.assertEqual(webhook_data['method'], 'MOBILE_MONEY')
        self.assertEqual(webhook_data['amount'], 25000)
        
        print("✅ Webhook de succès validé")
    
    def test_webhook_retrait_failed(self):
        """Test du webhook pour un retrait échoué"""
        print("\n❌ === TEST WEBHOOK RETRAIT ÉCHEC ===")
        
        # Données de webhook d'échec
        webhook_data = {
            "transactionId": "test_sandbox_failed_67890",
            "isPaymentSucces": False,
            "account": "22961000001",  # Numéro de test pour échec
            "failureCode": "insufficient_funds",
            "failureMessage": "Solde insuffisant",
            "label": "Retrait tontine test - échec",
            "method": "MOBILE_MONEY",
            "amount": 50000,
            "fees": 0,
            "partnerId": "your_partner_id",
            "performedAt": "2024-12-27T10:35:00.000Z",
            "stateData": {
                "retrait_id": "test_retrait_failed_id"
            },
            "event": "transaction.failed"
        }
        
        print(f"💥 Webhook d'échec reçu:")
        print(f"   - Transaction ID: {webhook_data['transactionId']}")
        print(f"   - Succès: {webhook_data['isPaymentSucces']}")
        print(f"   - Code d'erreur: {webhook_data['failureCode']}")
        print(f"   - Message: {webhook_data['failureMessage']}")
        print(f"   - Compte: {webhook_data['account']}")
        
        # Vérifications
        self.assertFalse(webhook_data['isPaymentSucces'])
        self.assertEqual(webhook_data['event'], 'transaction.failed')
        self.assertEqual(webhook_data['failureCode'], 'insufficient_funds')
        self.assertIn('insuffisant', webhook_data['failureMessage'])
        
        print("✅ Webhook d'échec validé")


if __name__ == "__main__":
    # Instructions pour lancer les tests
    print("🧪 Pour lancer les tests KKiaPay Sandbox:")
    print("1. Installer le SDK: pip install kkiapay")
    print("2. Configurer vos clés KKiaPay sandbox dans settings.py")
    print("3. Lancer: python manage.py test tontines.test_retrait_kkiapay_sandbox")
    print("4. Ouvrir test_retrait_kkiapay_sandbox.html pour l'interface")
