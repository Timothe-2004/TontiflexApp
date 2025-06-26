# Créer ce fichier: check_mobile_money.py
import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tontiflex.settings')
django.setup()

from mobile_money.models import OperateurMobileMoney, TransactionMobileMoney
from accounts.models import Client
from tontines.models import Tontine, Adhesion, Cotisation
from django.db import connection

def check_mobile_money_status():
    print("=" * 60)
    print("ÉTAT DU SYSTÈME MOBILE MONEY")
    print("=" * 60)
    
    # 1. Vérifier les opérateurs configurés
    operateurs = OperateurMobileMoney.objects.all()
    print(f"\n📱 OPÉRATEURS CONFIGURÉS ({operateurs.count()}):")
    for op in operateurs:
        print(f"  - {op.nom} ({op.code})")
        print(f"    Préfixes: {op.prefixes_telephone}")
        print(f"    API URL: {op.api_base_url}")
        print(f"    Frais: {op.frais_pourcentage}% + {op.frais_fixe} FCFA")
        print(f"    Limites: {op.montant_minimum} - {op.montant_maximum} FCFA")
        print()
    
    # 2. Vérifier les transactions
    transactions = TransactionMobileMoney.objects.all()
    print(f"💳 TRANSACTIONS MOBILE MONEY ({transactions.count()}):")
    for trans in transactions[:10]:  # Afficher les 10 dernières
        print(f"  - {trans.numero_transaction} | {trans.montant} FCFA")
        print(f"    {trans.operateur.nom} | Statut: {trans.statut}")
        print(f"    Client: {trans.client} | Date: {trans.date_creation}")
        print()
    
    # 3. Vérifier les adhésions avec paiement
    adhesions = Adhesion.objects.filter(
        operateur_mobile_money__isnull=False
    )
    print(f"🤝 ADHÉSIONS AVEC MOBILE MONEY ({adhesions.count()}):")
    for adh in adhesions[:5]:
        print(f"  - Client: {adh.client}")
        print(f"    Tontine: {adh.tontine.nom}")
        print(f"    Montant: {adh.montant_mise} FCFA")
        print(f"    Opérateur: {adh.operateur_mobile_money}")
        print(f"    Téléphone: {adh.numero_telephone_paiement}")
        print(f"    Statut: {adh.statut_actuel}")
        print()
    
    # 4. Vérifier les cotisations
    cotisations = Cotisation.objects.all()
    print(f"💰 COTISATIONS ({cotisations.count()}):")
    for cot in cotisations[:5]:
        print(f"  - Client: {cot.client}")
        print(f"    Montant: {cot.montant} FCFA")
        print(f"    Statut: {cot.statut}")
        print(f"    Transaction: {cot.numero_transaction}")
        print()

def check_database_tables():
    print("=" * 60)
    print("TABLES DE LA BASE DE DONNÉES")
    print("=" * 60)
    
    with connection.cursor() as cursor:
        # Lister toutes les tables
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'django_%' 
            ORDER BY name;
        """)
        tables = cursor.fetchall()
        
        print("📊 TABLES PRINCIPALES:")
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  - {table_name}: {count} enregistrements")

def test_mobile_money_integration():
    print("=" * 60)
    print("TEST D'INTÉGRATION MOBILE MONEY")
    print("=" * 60)
    
    # Vérifier si les API keys sont configurées
    from django.conf import settings
    
    mobile_money_settings = getattr(settings, 'MOBILE_MONEY', {})
    print("🔑 CONFIGURATION MOBILE MONEY:")
    
    if mobile_money_settings:
        for operator, config in mobile_money_settings.items():
            print(f"  {operator}:")
            for key, value in config.items():
                # Masquer les clés sensibles
                if 'key' in key.lower() or 'secret' in key.lower():
                    value = '*' * len(str(value)) if value else 'NON CONFIGURÉ'
                print(f"    {key}: {value}")
    else:
        print("  ⚠️  Configuration Mobile Money non trouvée dans settings.py")
    
    # Vérifier les vues Mobile Money
    print("\n🔗 URLS MOBILE MONEY DISPONIBLES:")
    try:
        from django.urls import reverse
        mobile_money_urls = [
            'transaction-list',
            'transaction-detail',
            'operateur-list',
        ]
        
        for url_name in mobile_money_urls:
            try:
                url = reverse(url_name)
                print(f"  ✅ {url_name}: {url}")
            except:
                print(f"  ❌ {url_name}: Non configuré")
    except Exception as e:
        print(f"  ⚠️  Erreur lors de la vérification des URLs: {e}")

if __name__ == "__main__":
    print("🚀 DIAGNOSTIC COMPLET DU SYSTÈME TONTIFLEX")
    print()
    
    try:
        check_mobile_money_status()
        print()
        check_database_tables()
        print()
        test_mobile_money_integration()
        
        print("\n" + "=" * 60)
        print("RECOMMANDATIONS:")
        print("=" * 60)
        print("1. Vérifiez les API keys dans settings.py")
        print("2. Testez les endpoints Mobile Money avec Postman")
        print("3. Consultez les logs pour les erreurs d'intégration")
        print("4. Utilisez Django Admin pour voir les données")
        
    except Exception as e:
        print(f"❌ Erreur lors du diagnostic: {e}")
        import traceback
        traceback.print_exc()