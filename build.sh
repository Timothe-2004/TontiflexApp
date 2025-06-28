#!/usr/bin/env bash
# Script de démarrage pour Render

set -o errexit  # Exit on error

# Collecter les fichiers statiques
python manage.py collectstatic --noinput

# Exécuter les migrations
python manage.py migrate

# Démarrer le serveur Gunicorn
gunicorn tontiflex.wsgi:application
