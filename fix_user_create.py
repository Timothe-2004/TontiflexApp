#!/usr/bin/env python3
"""
Script pour ajouter automatiquement le paramètre username aux appels User.objects.create_user()
dans le fichier de tests loans.
"""

import re

# Lire le fichier
with open(r"c:\Users\HOMEKOU\Downloads\Projet mémoire\app\tontiflex\loans\tests.py", "r", encoding="utf-8") as f:
    content = f.read()

# Compteur pour des noms d'utilisateur uniques
username_counter = 1

def replace_create_user(match):
    global username_counter
    
    # Extraire l'indentation et les paramètres
    indent = match.group(1)
    params = match.group(2)
    
    # Créer un nom d'utilisateur unique
    username = f"user{username_counter}"
    username_counter += 1
    
    # Ajouter le paramètre username au début
    new_params = f"\n{indent}    username=\"{username}\",{params}"
    
    return f"{indent}User.objects.create_user({new_params}\n{indent})"

# Pattern pour matcher User.objects.create_user( ... )
pattern = r'(\s+)User\.objects\.create_user\((.*?)\n\s+\)'

# Remplacer toutes les occurrences
content = re.sub(pattern, replace_create_user, content, flags=re.DOTALL)

# Écrire le fichier modifié
with open(r"c:\Users\HOMEKOU\Downloads\Projet mémoire\app\tontiflex\loans\tests.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Script terminé. Paramètre username ajouté à tous les appels User.objects.create_user()")
