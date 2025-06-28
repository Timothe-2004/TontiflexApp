#!/usr/bin/env bash
# Script de build pour Render

set -o errexit  # Exit on error

# Installer les dépendances Python
pip install -r requirements.txt

# Collecter les fichiers statiques
python manage.py collectstatic --noinput

# Exécuter les migrations
python manage.py migrate
