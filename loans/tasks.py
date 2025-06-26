"""
TÂCHES UTILITAIRES POUR LE MODULE PRÊTS - TONTIFLEX

Ce module contient des fonctions utilitaires pour:
1. Notifications automatiques (email/SMS)
2. Calculs de pénalités de retard
3. Mise à jour des statuts automatiques
4. Génération de rapports périodiques
5. Intégration avec Mobile Money pour les remboursements

Note: Ces fonctions peuvent être appelées directement ou via un scheduler
"""

import logging
from decimal import Decimal
from datetime import datetime, timedelta, date
from django.utils import timezone
from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F

logger = logging.getLogger(__name__)


# =============================================================================
# NOTIFICATIONS EMAILS ET SMS
# =============================================================================

def envoyer_notification_demande_soumise(demande_id):
    """
    Envoie une notification de confirmation de soumission de demande.
    
    Args:
        demande_id: ID de la demande de prêt
    """
    try:
        from .models import LoanApplication
        
        demande = LoanApplication.objects.get(id=demande_id)
        
        # Email de confirmation au client
        sujet = f"TontiFlex - Confirmation de votre demande de prêt #{demande.id}"
        message = f"""
        Bonjour {demande.client.nom_complet},
        
        Votre demande de prêt de {demande.montant_demande} FCFA a été soumise avec succès.
        
        Numéro de demande: {demande.id}
        Statut: En attente d'examen
        
        Vous recevrez une notification dès que votre demande sera traitée.
        
        Cordialement,
        L'équipe TontiFlex
        """
        
        if hasattr(settings, 'DEFAULT_FROM_EMAIL'):
            send_mail(
                sujet,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [demande.client.email],
                fail_silently=True
            )
        
        logger.info(f"Notification envoyée pour demande {demande_id}")
        
    except Exception as e:
        logger.error(f"Erreur envoi notification demande {demande_id}: {str(e)}")


def envoyer_notification_demande_traitee(demande_id, nouveau_statut):
    """
    Envoie une notification de traitement de demande.
    
    Args:
        demande_id: ID de la demande de prêt
        nouveau_statut: Nouveau statut de la demande
    """
    try:
        from .models import LoanApplication
        
        demande = LoanApplication.objects.get(id=demande_id)
        
        statuts_messages = {
            'ACCEPTE': 'acceptée',
            'REFUSE': 'refusée',
            'EN_EXAMEN': 'en cours d\'examen',
            'TRANSFERE_ADMIN': 'transférée pour validation finale'
        }
        
        message_statut = statuts_messages.get(nouveau_statut, 'mise à jour')
        
        sujet = f"TontiFlex - Mise à jour de votre demande de prêt #{demande.id}"
        message = f"""
        Bonjour {demande.client.nom_complet},
        
        Votre demande de prêt #{demande.id} a été {message_statut}.
        
        Statut actuel: {demande.get_statut_display()}
        
        Connectez-vous à votre espace client pour plus de détails.
        
        Cordialement,
        L'équipe TontiFlex
        """
        
        if hasattr(settings, 'DEFAULT_FROM_EMAIL'):
            send_mail(
                sujet,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [demande.client.email],
                fail_silently=True
            )
        
        logger.info(f"Notification statut envoyée pour demande {demande_id}")
        
    except Exception as e:
        logger.error(f"Erreur notification statut demande {demande_id}: {str(e)}")


# =============================================================================
# CALCULS PÉNALITÉS ET ÉCHÉANCES
# =============================================================================

def calculer_penalites_quotidiennes():
    """
    Calcule et applique les pénalités quotidiennes pour tous les prêts en retard.
    Fonction à exécuter quotidiennement via cron ou tâche programmée.
    """
    try:
        from .models import Loan, RepaymentSchedule
        from .utils import calculer_penalite_retard
        
        # Obtenir tous les prêts actifs avec échéances en retard
        today = timezone.now().date()
        
        echeances_retard = RepaymentSchedule.objects.filter(
            loan__statut='ACTIVE',
            date_due__lt=today,
            amount_paid__lt=F('amount_due')
        )
        
        for echeance in echeances_retard:
            loan = echeance.loan
            
            # Calculer nombre de jours de retard
            jours_retard = (today - echeance.date_due).days
            
            if jours_retard > 0:
                # Calculer pénalité
                penalite = calculer_penalite_retard(
                    echeance.amount_due - echeance.amount_paid,
                    jours_retard,
                    loan.taux_penalite
                )
                
                # Ajouter à la pénalité totale
                echeance.penalty_amount += penalite
                echeance.save()
                
                logger.info(f"Pénalité {penalite} appliquée à l'échéance {echeance.id}")
        
        logger.info("Calcul pénalités quotidiennes terminé")
        
    except Exception as e:
        logger.error(f"Erreur calcul pénalités: {str(e)}")


def envoyer_rappels_echeances():
    """
    Envoie des rappels d'échéances à venir (3 jours avant échéance).
    """
    try:
        from .models import RepaymentSchedule
        
        # Échéances dans 3 jours
        date_rappel = timezone.now().date() + timedelta(days=3)
        
        echeances_rappel = RepaymentSchedule.objects.filter(
            date_due=date_rappel,
            amount_paid__lt=F('amount_due'),
            loan__statut='ACTIVE'
        )
        
        for echeance in echeances_rappel:
            loan = echeance.loan
            client = loan.application.client
            
            montant_restant = echeance.amount_due - echeance.amount_paid
            
            sujet = f"TontiFlex - Rappel échéance prêt #{loan.id}"
            message = f"""
            Bonjour {client.nom_complet},
            
            Rappel: Votre prochaine échéance de prêt arrive à échéance dans 3 jours.
            
            Date d'échéance: {echeance.date_due.strftime('%d/%m/%Y')}
            Montant à payer: {montant_restant} FCFA
            
            Vous pouvez effectuer votre remboursement via Mobile Money.
            
            Cordialement,
            L'équipe TontiFlex
            """
            
            if hasattr(settings, 'DEFAULT_FROM_EMAIL'):
                send_mail(
                    sujet,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [client.email],
                    fail_silently=True
                )
        
        logger.info(f"Rappels envoyés pour {echeances_rappel.count()} échéances")
        
    except Exception as e:
        logger.error(f"Erreur envoi rappels: {str(e)}")


# =============================================================================
# RAPPORTS ET STATISTIQUES
# =============================================================================

def generer_rapport_mensuel_prets():
    """
    Génère le rapport mensuel des prêts pour les administrateurs.
    """
    try:
        from .models import LoanApplication, Loan
        from .utils import calculer_statistiques_prets
        
        # Statistiques du mois en cours
        debut_mois = timezone.now().replace(day=1)
        fin_mois = debut_mois + timedelta(days=32)
        fin_mois = fin_mois.replace(day=1) - timedelta(days=1)
        
        stats = calculer_statistiques_prets(debut_mois, fin_mois)
        
        # Génération rapport
        rapport = f"""
        RAPPORT MENSUEL DES PRÊTS - {debut_mois.strftime('%B %Y')}
        
        Nouvelles demandes: {stats['nouvelles_demandes']}
        Prêts accordés: {stats['prets_accordes']}
        Montant total accordé: {stats['montant_total_accorde']} FCFA
        Taux d'approbation: {stats['taux_approbation']}%
        
        Remboursements reçus: {stats['remboursements_recus']} FCFA
        Prêts en retard: {stats['prets_retard']}
        Pénalités collectées: {stats['penalites_collectees']} FCFA
        """
        
        # Envoi aux administrateurs
        # TODO: Implémenter envoi email aux admins
        
        logger.info("Rapport mensuel généré")
        
    except Exception as e:
        logger.error(f"Erreur génération rapport: {str(e)}")


# =============================================================================
# INTÉGRATION MOBILE MONEY
# =============================================================================

def traiter_remboursement_mobile_money(payment_id):
    """
    Traite un remboursement via Mobile Money.
    
    Args:
        payment_id: ID du paiement à traiter
    """
    try:
        from .models import Payment
        
        payment = Payment.objects.get(id=payment_id)
        
        # Traitement via Mobile Money
        # TODO: Intégrer avec les services Mobile Money existants
        
        logger.info(f"Remboursement {payment_id} traité")
        
    except Exception as e:
        logger.error(f"Erreur traitement remboursement {payment_id}: {str(e)}")


# =============================================================================
# MAINTENANCE SYSTÈME
# =============================================================================

def nettoyer_documents_temporaires():
    """
    Nettoie les documents temporaires et anciens.
    """
    try:
        # TODO: Implémenter nettoyage documents
        logger.info("Nettoyage documents terminé")
        
    except Exception as e:
        logger.error(f"Erreur nettoyage: {str(e)}")


def archiver_prets_anciens():
    """
    Archive les prêts complètement remboursés et anciens.
    """
    try:
        from .models import Loan
        
        # Prêts remboursés depuis plus de 2 ans
        date_limite = timezone.now() - timedelta(days=730)
        
        prets_archives = Loan.objects.filter(
            statut='REMBOURSE',
            date_remboursement_complet__lt=date_limite
        )
        
        # TODO: Implémenter archivage
        
        logger.info(f"Archivage de {prets_archives.count()} prêts")
        
    except Exception as e:
        logger.error(f"Erreur archivage: {str(e)}")
