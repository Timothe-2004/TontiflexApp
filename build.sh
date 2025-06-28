#!/usr/bin/env bash
# Script de build pour Render

set -o errexit  # Exit on error

# Installer les dépendances Python avec versions compatibles
pip install -r requirements-render.txt

# Collecter les fichiers statiques
python manage.py collectstatic --noinput

# Exécuter les migrations
python manage.py migrate
