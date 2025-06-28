#!/usr/bin/env python3
"""
🔍 Script de Vérification de Déploiement TontiFlex
=================================================

Vérifie que tous les composants sont prêts pour le déploiement sur Render.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_file_exists(filepath, description):
    """Vérifie qu'un fichier existe"""
    if Path(filepath).exists():
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description}: {filepath} - MANQUANT")
        return False

def check_requirements():
    """Vérifie les fichiers requirements"""
    print("\n📦 Vérification des Requirements:")
    
    files_ok = True
    files_ok &= check_file_exists("requirements.txt", "Requirements de base")
    files_ok &= check_file_exists("requirements-production.txt", "Requirements de production")
    
    # Vérifier les dépendances critiques
    if Path("requirements-production.txt").exists():
        with open("requirements-production.txt", "r") as f:
            content = f.read()
            
        critical_deps = [
            "django>=5.2.0",
            "gunicorn>=23.0.0",
            "whitenoise>=6.9.0",
            "dj-database-url>=3.0.0",
            "psycopg2-binary>=2.9.10",
            "kkiapay==0.0.6",
            "requests==2.22.0"
        ]
        
        for dep in critical_deps:
            if dep.split(">=")[0].split("==")[0] in content:
                print(f"✅   {dep}")
            else:
                print(f"❌   {dep} - MANQUANT")
                files_ok = False
    
    return files_ok

def check_build_script():
    """Vérifie le script de build"""
    print("\n🔨 Vérification du Script de Build:")
    
    if not check_file_exists("build.sh", "Script de build"):
        return False
    
    # Vérifier que le script est exécutable
    try:
        result = subprocess.run(['ls', '-la', 'build.sh'], capture_output=True, text=True)
        if 'x' in result.stdout:
            print("✅ build.sh est exécutable")
        else:
            print("⚠️  build.sh pourrait ne pas être exécutable (chmod +x build.sh)")
    except:
        print("⚠️  Impossible de vérifier les permissions de build.sh")
    
    return True

def check_render_config():
    """Vérifie la configuration Render"""
    print("\n⚙️  Vérification de la Configuration Render:")
    
    return check_file_exists("render.yaml", "Configuration Render")

def check_django_settings():
    """Vérifie les settings Django"""
    print("\n🔧 Vérification des Settings Django:")
    
    settings_file = "tontiflex/settings.py"
    if not check_file_exists(settings_file, "Settings Django"):
        return False
    
    with open(settings_file, "r") as f:
        content = f.read()
    
    # Vérifications critiques
    checks = [
        ("ALLOWED_HOSTS", "Configuration ALLOWED_HOSTS"),
        ("whitenoise", "WhiteNoise middleware"),
        ("dj_database_url", "Support PostgreSQL"),
        ("STATIC_ROOT", "Configuration fichiers statiques"),
        ("KKIAPAY_WEBHOOK_URL", "Configuration webhook KKiaPay"),
        ("tontiflexapp.onrender.com", "URL de production")
    ]
    
    all_ok = True
    for check, description in checks:
        if check in content:
            print(f"✅ {description}")
        else:
            print(f"❌ {description} - MANQUANT")
            all_ok = False
    
    return all_ok

def check_git_status():
    """Vérifie le statut Git"""
    print("\n📝 Vérification du Statut Git:")
    
    try:
        # Vérifier s'il y a des changements non commités
        result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        if result.stdout.strip():
            print("⚠️  Il y a des changements non commités:")
            print(result.stdout)
        else:
            print("✅ Tous les changements sont commités")
        
        # Vérifier la branche actuelle
        result = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True)
        branch = result.stdout.strip()
        print(f"📍 Branche actuelle: {branch}")
        
        if branch != "main":
            print("⚠️  Vous n'êtes pas sur la branche 'main'")
        
        return True
    except:
        print("❌ Git n'est pas configuré ou accessible")
        return False

def check_environment_variables():
    """Vérifie les variables d'environnement critiques"""
    print("\n🌍 Variables d'Environnement Critiques pour Render:")
    
    critical_vars = [
        "DEBUG",
        "SECRET_KEY", 
        "DATABASE_URL",
        "KKIAPAY_PUBLIC_KEY",
        "KKIAPAY_PRIVATE_KEY",
        "KKIAPAY_SECRET_KEY",
        "KKIAPAY_WEBHOOK_URL",
        "ALLOWED_HOSTS"
    ]
    
    print("📋 À configurer sur Render:")
    for var in critical_vars:
        print(f"   - {var}")
    
    return True

def main():
    """Fonction principale"""
    print("🚀 Vérification de Déploiement TontiFlex sur Render")
    print("=" * 55)
    
    # Vérifier qu'on est dans le bon répertoire
    if not Path("manage.py").exists():
        print("❌ ERREUR: Ce script doit être exécuté depuis la racine du projet Django")
        sys.exit(1)
    
    all_checks = [
        check_requirements(),
        check_build_script(),
        check_render_config(),
        check_django_settings(),
        check_git_status(),
        check_environment_variables()
    ]
    
    print("\n" + "=" * 55)
    
    if all(all_checks):
        print("🎉 SUCCÈS: Votre projet est prêt pour le déploiement sur Render!")
        print("\n📚 Prochaines étapes:")
        print("1. Pusher les changements: git push origin main")
        print("2. Créer un Web Service sur https://dashboard.render.com")
        print("3. Configurer les variables d'environnement")
        print("4. Voir RENDER_DEPLOYMENT_GUIDE.md pour les détails")
    else:
        print("⚠️  ATTENTION: Certaines vérifications ont échoué")
        print("Corrigez les problèmes avant de déployer.")
        sys.exit(1)

if __name__ == "__main__":
    main()
