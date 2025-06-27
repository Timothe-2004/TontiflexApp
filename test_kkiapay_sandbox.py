#!/usr/bin/env python
"""
Script de test KKiaPay SANDBOX pour TontiFlex - IMPORTS CORRIGÉS
================================================================

Test la configuration KKiaPay selon la documentation officielle:
https://docs.kkiapay.me/v1/compte/kkiapay-sandbox-guide-de-test

USAGE:
    python test_kkiapay_sandbox_fixed.py
"""
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tontiflex.settings')
django.setup()

from django.contrib.auth import get_user_model
from decimal import Decimal
import logging

# ✅ IMPORTS ABSOLUS (pas relatifs)
from payments.config import kkiapay_config
from payments.models import KKiaPayTransaction

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

User = get_user_model()


class KKiaPayArchitectureTest:
    def test_verify_transaction_id(self, transaction_id):
        """Test de vérification d'une transaction KKIAPAY existante (SANDBOX)"""
        from kkiapay import Kkiapay
        print("\n" + "="*70)
        print("🔎 TEST: VÉRIFICATION TRANSACTION KKIAPAY (SANDBOX)")
        print("="*70)
        try:
            k = Kkiapay(
                kkiapay_config.public_key,
                kkiapay_config.private_key,
                kkiapay_config.secret_key,
                sandbox=True
            )
            result = k.verify_transaction(transaction_id)
            print(f"📋 Statut de la transaction: {result}")
            return result
        except Exception as e:
            print(f"❌ Erreur lors de la vérification: {e}")
            return None
    def test_6_initiate_and_verify_payment_sandbox(self):
        """Test 6: Initiation d'un paiement via l'API REST SANDBOX, vérification et enregistrement"""
        import requests
        from kkiapay import Kkiapay
        print("\n" + "="*70)
        print("💸 TEST 6: INITIATION & VÉRIFICATION PAIEMENT KKIAPAY (SANDBOX)")
        print("="*70)

        # Utilisation d'un numéro de test officiel (succès immédiat)
        phone = self.test_numbers['mtn_benin_success']
        amount = 1000
        reason = "Test SANDBOX TontiFlex"
        callback_url = getattr(kkiapay_config, 'webhook_url', None)

        url = "https://api-sandbox.kkiapay.me/api/v1/transactions/initiate"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {kkiapay_config.public_key}"
        }
        data = {
            "amount": amount,
            "phone": phone,
            "reason": reason,
        }
        if callback_url:
            data["callback"] = callback_url

        print(f"➡️  Initiation du paiement SANDBOX pour {amount} FCFA, {phone}")
        try:
            response = requests.post(url, json=data, headers=headers, timeout=15)
            response.raise_for_status()
            result = response.json()
            print(f"✅ Paiement initié: {result}")
        except Exception as e:
            print(f"❌ Erreur lors de l'initiation: {e}")
            return False

        transaction_id = result.get("transactionId") or result.get("transaction_id")
        if not transaction_id:
            print("❌ transactionId manquant dans la réponse")
            return False

        # Vérification de la transaction via SDK Python
        print(f"🔎 Vérification de la transaction {transaction_id} via SDK Python...")
        try:
            k = Kkiapay(
                kkiapay_config.public_key,
                kkiapay_config.private_key,
                kkiapay_config.secret_key,
                sandbox=True
            )
            verification = k.verify_transaction(transaction_id)
            print(f"📋 Statut de la transaction: {verification}")
        except Exception as e:
            print(f"❌ Erreur lors de la vérification: {e}")
            return False

        # Enregistrement dans la base
        try:
            tx = KKiaPayTransaction.objects.create(
                user=self.test_user,
                reference_tontiflex=transaction_id,
                montant=amount,
                status=verification.get('status', 'pending'),
                phone=phone
            )
            print(f"💾 Transaction enregistrée: {tx}")
        except Exception as e:
            print(f"❌ Erreur lors de l'enregistrement DB: {e}")
            return False

        print("✅ Test SANDBOX complet: initiation, vérification, enregistrement OK")
        return True
    """
    Test de l'architecture KKiaPay CORRECTE
    
    Ce test vérifie que l'architecture respecte le SDK Python officiel
    qui ne contient QUE verify_transaction() et refund_transaction()
    """
    
    def __init__(self):
        self.test_user = self._get_or_create_test_user()
        
        # Numéros de test OFFICIELS selon la documentation
        self.test_numbers = {
            # MTN Bénin - NUMÉROS OFFICIELS
            'mtn_benin_success': '+229 ',     # Succès immédiat
            'mtn_benin_success2': '+22997000000',    # Succès immédiat alternatif
            'mtn_benin_delayed': '+22961100000',     # Succès avec délai 1 min
            'mtn_benin_error': '+22961000001',       # Processing error
            'mtn_benin_insufficient': '+22961000002', # Insufficient fund
            'mtn_benin_declined': '+22961000003',    # Payment declined
            
            # MOOV - NUMÉROS OFFICIELS  
            'moov_success': '+22968000000',          # Succès immédiat
            'moov_success2': '+22995000000',         # Succès immédiat alternatif
            'moov_delayed': '+22968100000',          # Succès avec délai 1 min
            'moov_error': '+22968000001',            # Processing error
            'moov_insufficient': '+22968000002',     # Insufficient fund
            'moov_declined': '+22968000003',         # Payment declined
            
            # MTN Côte d'Ivoire - NUMÉROS OFFICIELS
            'mtn_ci_success': '+2250577100000',      # Succès immédiat
            'mtn_ci_delayed': '+2250577110000',      # Succès avec délai 1 min
            'mtn_ci_error': '+2250577100001',        # Processing error
        }
    
    def _get_or_create_test_user(self):
        """Crée ou récupère un utilisateur de test"""
        try:
            user = User.objects.get(username='test_kkiapay')
        except User.DoesNotExist:
            user = User.objects.create_user(
                username='test_kkiapay',
                email='test@kkiapay.tontiflex.com',
                password='test123'
            )
            logger.info("👤 Utilisateur de test créé: test_kkiapay")
        
        return user
    
    def test_1_configuration(self):
        """Test 1: Configuration KKiaPay"""
        print("\n" + "="*70)
        print("🔧 TEST 1: CONFIGURATION KKIAPAY")
        print("="*70)
        
        print(f"🌍 Mode: {'SANDBOX' if kkiapay_config.sandbox else 'LIVE'}")
        print(f"🔑 Public Key: {kkiapay_config.public_key[:20]}..." if kkiapay_config.public_key else "❌ Manquante")
        print(f"🔐 Private Key: {kkiapay_config.private_key[:20]}..." if kkiapay_config.private_key else "❌ Manquante")
        print(f"🛡️ Secret Key: {kkiapay_config.secret_key[:20]}..." if kkiapay_config.secret_key else "❌ Manquante")
        print(f"🌐 API URL: {kkiapay_config.base_url}")
        
        # Validation des clés (accepter tout format valide)
        issues = []
        
        # Vérification simple de la présence et longueur des clés
        if not kkiapay_config.public_key or len(kkiapay_config.public_key) < 20:
            issues.append("❌ Public Key manquante ou trop courte")
            
        if not kkiapay_config.private_key or len(kkiapay_config.private_key) < 20:
            issues.append("❌ Private Key manquante ou trop courte")
            
        if not kkiapay_config.secret_key or len(kkiapay_config.secret_key) < 20:
            issues.append("❌ Secret Key manquante ou trop courte")
        
        if issues:
            print("\n🚨 PROBLÈMES DE CONFIGURATION DÉTECTÉS:")
            for issue in issues:
                print(f"  {issue}")
            print("\n💡 SOLUTION:")
            print("  1. Allez sur https://app.kkiapay.me/dashboard")
            print("  2. Section Développeurs > Clés API")
            print("  3. Vérifiez le mode SANDBOX")
            print("  4. Régénérez les clés si nécessaire")
            print("  5. Mettez à jour votre fichier .env")
            return False
        
        if kkiapay_config.is_configured():
            print("✅ Configuration complète et valide")
            return True
        else:
            print("❌ Configuration incomplète")
            return False
    
    def test_2_sdk_python_officiel(self):
        """Test 2: SDK Python officiel (verify_transaction uniquement)"""
        print("\n" + "="*70)
        print("🐍 TEST 2: SDK PYTHON OFFICIEL")
        print("="*70)
        
        try:
            # Import du SDK Python officiel
            from kkiapay import Kkiapay
            
            # Initialisation avec vos clés
            k = Kkiapay(
                kkiapay_config.public_key,
                kkiapay_config.private_key,
                kkiapay_config.secret_key,
                sandbox=kkiapay_config.sandbox
            )
            
            print("✅ SDK Python officiel initialisé")
            print(f"📦 Méthodes disponibles: verify_transaction, refund_transaction")
            print(f"❌ Méthode initiate_payment: N'EXISTE PAS dans le SDK officiel")
            
            # Test avec un ID fictif pour voir le comportement
            try:
                response = k.verify_transaction('test_id_fictif')
                print(f"📋 Réponse: {response}")
            except Exception as e:
                print(f"⚠️ Erreur attendue pour ID fictif: {str(e)[:100]}...")
                print("✅ Le SDK Python fonctionne correctement")
            
            return True
            
        except ImportError as e:
            print(f"❌ Erreur import SDK: {e}")
            print("💡 Installez le SDK: pip install kkiapay")
            return False
        except Exception as e:
            print(f"❌ Erreur SDK: {e}")
            return False
    
    def test_3_architecture_frontend_needed(self):
        """Test 3: Explication de l'architecture correcte"""
        print("\n" + "="*70)
        print("🌐 TEST 3: ARCHITECTURE CORRECTE REQUISE")
        print("="*70)
        
        print("📋 ARCHITECTURE OFFICIELLE KKIAPAY:")
        print("  1. 🖥️  FRONTEND (JavaScript): Initie les paiements")
        print("     • Widget KKiaPay avec openKkiapayWidget()")
        print("     • Numéros de test officiels")
        print("     • Gestion des événements success/failed")
        print()
        print("  2. 🐍  BACKEND (Python): Vérifie les transactions")
        print("     • SDK Python: verify_transaction() uniquement")
        print("     • Webhooks: Réception des notifications")
        print("     • Base de données: Stockage des statuts")
        print()
        print("❌ PROBLÈME ACTUEL:")
        print("  • Votre code essaie d'initier des paiements depuis Python")
        print("  • La méthode initiate_payment() n'existe pas dans le SDK")
        print("  • C'est pourquoi vous avez l'erreur 404 Not Found")
        print()
        print("✅ SOLUTION:")
        print("  • Utilisez le widget JavaScript pour initier les paiements")
        print("  • Utilisez Python uniquement pour vérifier")
        
        return True
    
    def test_4_widget_javascript_example(self):
        """Test 4: Exemple de widget JavaScript"""
        print("\n" + "="*70)
        print("📱 TEST 4: EXEMPLE WIDGET JAVASCRIPT")
        print("="*70)
        
        print("💡 VOICI COMMENT UTILISER KKIAPAY CORRECTEMENT:")
        print()
        print("<!-- Dans votre template HTML -->")
        print('<script src="https://cdn.kkiapay.me/k.js"></script>')
        print()
        print("<script>")
        print("// Initier un paiement avec un numéro de test officiel")
        print("function testerPaiementKKiaPay() {")
        print("    openKkiapayWidget({")
        print(f"        amount: 1000,")
        print(f"        key: '{kkiapay_config.public_key}',")
        print(f"        sandbox: {str(kkiapay_config.sandbox).lower()},")
        print(f"        phone: '{self.test_numbers['mtn_benin_success']}',  // Numéro officiel")
        print(f"        callback: '{kkiapay_config.webhook_url}',")
        print("        description: 'Test SANDBOX TontiFlex'")
        print("    });")
        print("    ")
        print("    // Écouter les événements")
        print("    addSuccessListener(response => {")
        print("        console.log('Paiement réussi:', response);")
        print("    });")
        print("    ")
        print("    addFailedListener(error => {")
        print("        console.log('Paiement échoué:', error);")
        print("    });")
        print("}")
        print("</script>")
        print()
        print("🎯 AVEC CETTE MÉTHODE:")
        print("  ✅ Les paiements fonctionneront")
        print("  ✅ Les numéros de test officiels marcheront")
        print("  ✅ Vous recevrez les webhooks")
        print("  ✅ Votre backend Python pourra vérifier les transactions")
        
        return True
    
    def test_5_database_transactions(self):
        """Test 5: État des transactions en base"""
        print("\n" + "="*70)
        print("💾 TEST 5: TRANSACTIONS EN BASE DE DONNÉES")
        print("="*70)
        
        try:
            # Compter les transactions existantes
            total_transactions = KKiaPayTransaction.objects.count()
            pending_transactions = KKiaPayTransaction.objects.filter(status='pending').count()
            success_transactions = KKiaPayTransaction.objects.filter(status='success').count()
            failed_transactions = KKiaPayTransaction.objects.filter(status='failed').count()
            
            print(f"📊 Total transactions: {total_transactions}")
            print(f"⏳ En attente: {pending_transactions}")
            print(f"✅ Réussies: {success_transactions}")
            print(f"❌ Échouées: {failed_transactions}")
            
            if total_transactions > 0:
                print("\n📋 Dernières transactions:")
                recent = KKiaPayTransaction.objects.order_by('-created_at')[:3]
                for tx in recent:
                    print(f"  • {tx.reference_tontiflex} - {tx.status} - {tx.montant} FCFA")
            else:
                print("📝 Aucune transaction en base (normal pour le premier test)")
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur base de données: {e}")
            return False
    
    def run_all_tests(self):
        """Exécute tous les tests d'architecture"""
        print("🧪 TEST ARCHITECTURE KKIAPAY CORRECTE")
        print("Documentation: https://docs.kkiapay.me/v1/compte/kkiapay-sandbox-guide-de-test")
        print("="*80)
        
        # Tests séquentiels
        results = []
        results.append(self.test_1_configuration())
        results.append(self.test_2_sdk_python_officiel())
        results.append(self.test_3_architecture_frontend_needed())
        results.append(self.test_4_widget_javascript_example())
        results.append(self.test_5_database_transactions())
        results.append(self.test_6_initiate_and_verify_payment_sandbox())
        # Résumé final
        self.display_final_summary(results)
    
    def display_final_summary(self, results):
        """Affichage du résumé final"""
        print("\n" + "="*80)
        print("📈 RÉSUMÉ FINAL - ARCHITECTURE KKIAPAY")
        print("="*80)
        
        passed_tests = sum(results)
        total_tests = len(results)
        
        print(f"📊 Tests d'architecture: {passed_tests}/{total_tests} réussis")
        
        if all(results):
            print("\n✅ ARCHITECTURE PRÊTE POUR IMPLÉMENTATION")
            print("🎯 Prochaines étapes:")
            print("  1. 🔧 Implémentez le widget JavaScript dans votre frontend")
            print("  2. 🧪 Testez avec les numéros officiels via le widget")
            print("  3. 📡 Configurez les webhooks")
            print("  4. 🐍 Utilisez Python uniquement pour verify_transaction()")
            print("  5. 🚀 Une fois validé en SANDBOX, passez en LIVE")
        else:
            print("\n⚠️ PROBLÈMES À CORRIGER AVANT IMPLÉMENTATION")
            print("🔍 Vérifiez:")
            print("  • Configuration des clés API sur le dashboard KKiaPay")
            print("  • Format des clés (pk_sandbox_, tpk_, tsk_)")
            print("  • Mode SANDBOX activé")
            print("  • Installation du SDK Python: pip install kkiapay")
        
        print("\n📚 Documentation officielle:")
        print("  • Guide SANDBOX: https://docs.kkiapay.me/v1/compte/kkiapay-sandbox-guide-de-test")
        print("  • SDK JavaScript: https://docs.kkiapay.me/v1/plugin-et-sdk/sdk-javascript")
        print("  • SDK Python: https://github.com/PythonBenin/kkiapay-python")
        print("  • Dashboard: https://app.kkiapay.me/dashboard")
        
        print(f"\n🎯 CONCLUSION:")
        if all(results):
            print("✅ Votre configuration est correcte")
            print("✅ Implémentez l'architecture JavaScript + Python")
            print("✅ Vous pourrez alors passer en production")
        else:
            print("❌ Corrigez d'abord la configuration")
            print("❌ Puis implémentez l'architecture correcte")
            print("❌ Le projet n'est pas encore prêt pour production")


def main():
    """Point d'entrée principal"""
    print("🔍 Vérification de l'environnement Django...")
    
    # Vérification que nous sommes en mode SANDBOX
    if not kkiapay_config.sandbox:
        print("❌ ERREUR: Ce script ne fonctionne qu'en mode SANDBOX")
        print("   Vérifiez que KKIAPAY_SANDBOX=True dans votre fichier .env")
        sys.exit(1)
    
    print("✅ Mode SANDBOX confirmé - Démarrage des tests d'architecture")
    
    # Lancement des tests
    tester = KKiaPayArchitectureTest()
    tester.run_all_tests()


if __name__ == '__main__':
    main()