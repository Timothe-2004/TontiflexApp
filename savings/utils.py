"""
Fonctions utilitaires pour le module Savings.
Logique métier et helpers pour les comptes épargne et transactions.
"""
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.db import transaction

# Import des modèles
from .models import SavingsAccount, SavingsTransaction
from accounts.models import User
from payments.models import KKiaPayTransaction  # MIGRATION : mobile_money → KKiaPay


logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTES MÉTIER
# ============================================================================

FRAIS_CREATION_COMPTE = Decimal('1000.00')  # 1000 FCFA
MONTANT_MINIMUM_DEPOT = Decimal('100.00')   # 100 FCFA
MONTANT_MINIMUM_RETRAIT = Decimal('500.00') # 500 FCFA
SOLDE_MINIMUM_COMPTE = Decimal('0.00')      # Pas de solde minimum


# ============================================================================
# VALIDATION MÉTIER
# ============================================================================

def valider_eligibilite_compte_epargne(client: User) -> dict:
    """
    Valide si un client peut créer un compte épargne.
    
    Args:
        client: Instance User du client
        
    Returns:
        dict: {'eligible': bool, 'raisons': list}
    """
    raisons = []
    
    # Vérifier le type d'utilisateur
    if client.type_utilisateur != User.TypeUtilisateur.CLIENT:
        raisons.append("Seuls les clients peuvent créer des comptes épargne")
    
    # Vérifier si le client a déjà un compte épargne
    compte_existant = SavingsAccount.objects.filter(
        client=client,
        statut__in=[
            SavingsAccount.StatutChoices.EN_ATTENTE,
            SavingsAccount.StatutChoices.APPROUVE,
            SavingsAccount.StatutChoices.ACTIF
        ]
    ).exists()
    
    if compte_existant:
        raisons.append("Le client a déjà un compte épargne actif ou en cours de validation")
    
    # Note: Le client n'a pas besoin d'être pré-associé à un SFD
    # L'association se fait lors de la validation par un agent SFD
    
    return {
        'eligible': len(raisons) == 0,
        'raisons': raisons
    }


def valider_montant_transaction(montant: Decimal, type_transaction: str) -> dict:
    """
    Valide le montant d'une transaction selon son type.
    
    Args:
        montant: Montant de la transaction
        type_transaction: Type de transaction ('DEPOT' ou 'RETRAIT')
        
    Returns:
        dict: {'valide': bool, 'erreur': str}
    """
    if montant <= 0:
        return {'valide': False, 'erreur': 'Le montant doit être positif'}
    
    if type_transaction == SavingsTransaction.TypeChoices.DEPOT:
        if montant < MONTANT_MINIMUM_DEPOT:
            return {
                'valide': False, 
                'erreur': f'Le montant minimum pour un dépôt est de {MONTANT_MINIMUM_DEPOT} FCFA'
            }
    
    elif type_transaction == SavingsTransaction.TypeChoices.RETRAIT:
        if montant < MONTANT_MINIMUM_RETRAIT:
            return {
                'valide': False, 
                'erreur': f'Le montant minimum pour un retrait est de {MONTANT_MINIMUM_RETRAIT} FCFA'
            }
    
    return {'valide': True, 'erreur': None}


def valider_solde_suffisant(compte: SavingsAccount, montant_retrait: Decimal) -> dict:
    """
    Valide si le solde du compte est suffisant pour un retrait.
    
    Args:
        compte: Instance SavingsAccount
        montant_retrait: Montant du retrait demandé
        
    Returns:
        dict: {'suffisant': bool, 'solde_actuel': Decimal, 'solde_apres': Decimal}
    """
    solde_actuel = compte.calculer_solde()
    solde_apres = solde_actuel - montant_retrait
    
    return {
        'suffisant': solde_apres >= SOLDE_MINIMUM_COMPTE,
        'solde_actuel': solde_actuel,
        'solde_apres': solde_apres
    }


# ============================================================================
# GESTION DES STATUTS
# ============================================================================

def obtenir_prochaine_action_compte(compte: SavingsAccount) -> str:
    """
    Détermine la prochaine action requise pour un compte épargne.
    
    Args:
        compte: Instance SavingsAccount
        
    Returns:
        str: Description de la prochaine action
    """
    if compte.statut == SavingsAccount.StatutChoices.EN_ATTENTE:
        return "En attente de validation par l'agent SFD"
    
    elif compte.statut == SavingsAccount.StatutChoices.APPROUVE:
        return "En attente du paiement des frais de création"
    
    elif compte.statut == SavingsAccount.StatutChoices.ACTIF:
        return "Compte actif - Dépôts et retraits disponibles"
    
    elif compte.statut == SavingsAccount.StatutChoices.REJETE:
        return "Demande rejetée - Contactez votre agent SFD"
    
    elif compte.statut == SavingsAccount.StatutChoices.SUSPENDU:
        return "Compte suspendu - Contactez l'administration"
    
    elif compte.statut == SavingsAccount.StatutChoices.FERME:
        return "Compte fermé"
    
    return "Statut inconnu"


def peut_effectuer_transaction(compte: SavingsAccount, type_transaction: str) -> dict:
    """
    Vérifie si une transaction peut être effectuée sur un compte.
    
    Args:
        compte: Instance SavingsAccount
        type_transaction: Type de transaction
        
    Returns:
        dict: {'autorise': bool, 'raison': str}
    """
    if compte.statut != SavingsAccount.StatutChoices.ACTIF:
        return {
            'autorise': False,
            'raison': f'Le compte doit être actif pour effectuer des transactions (statut actuel: {compte.get_statut_display()})'
        }
    
    return {'autorise': True, 'raison': None}


# ============================================================================
# CALCULS FINANCIERS
# ============================================================================

def calculer_frais_transaction(montant: Decimal, type_transaction: str, operateur: str) -> Decimal:
    """
    Calcule les frais d'une transaction Mobile Money.
    
    Args:
        montant: Montant de la transaction
        type_transaction: Type de transaction
        operateur: Opérateur Mobile Money
        
    Returns:
        Decimal: Montant des frais
    """
    # Frais basiques selon l'opérateur (à adapter selon les tarifs réels)
    if operateur == SavingsAccount.OperateurChoices.MTN:
        if montant <= 1000:
            return Decimal('50.00')
        elif montant <= 5000:
            return Decimal('100.00')
        elif montant <= 25000:
            return Decimal('200.00')
        else:
            return Decimal('500.00')
    
    elif operateur == SavingsAccount.OperateurChoices.MOOV:
        if montant <= 1000:
            return Decimal('60.00')
        elif montant <= 5000:
            return Decimal('120.00')
        elif montant <= 25000:
            return Decimal('250.00')
        else:
            return Decimal('600.00')
    
    # Frais par défaut
    return Decimal('100.00')


def calculer_statistiques_compte(compte: SavingsAccount) -> dict:
    """
    Calcule les statistiques d'un compte épargne.
    
    Args:
        compte: Instance SavingsAccount
        
    Returns:
        dict: Statistiques du compte
    """
    transactions = compte.transactions.filter(
        statut=SavingsTransaction.StatutChoices.CONFIRMEE
    )
    
    depots = transactions.filter(type_transaction=SavingsTransaction.TypeChoices.DEPOT)
    retraits = transactions.filter(type_transaction=SavingsTransaction.TypeChoices.RETRAIT)
    
    total_depots = sum(t.montant for t in depots)
    total_retraits = sum(t.montant for t in retraits)
    
    return {
        'solde_actuel': compte.calculer_solde(),
        'nombre_transactions': transactions.count(),
        'nombre_depots': depots.count(),
        'nombre_retraits': retraits.count(),
        'total_depots': total_depots,
        'total_retraits': total_retraits,
        'transaction_moyenne': (total_depots + total_retraits) / max(transactions.count(), 1),
        'derniere_transaction': transactions.first().date_confirmation if transactions.exists() else None
    }


# ============================================================================
# UTILITAIRES DE FORMATAGE
# ============================================================================

def formater_reference_transaction(compte: SavingsAccount, type_transaction: str) -> str:
    """
    Génère une référence unique pour une transaction.
    
    Args:
        compte: Instance SavingsAccount
        type_transaction: Type de transaction
        
    Returns:
        str: Référence formatée
    """
    now = timezone.now()
    prefix = 'DEP' if type_transaction == SavingsTransaction.TypeChoices.DEPOT else 'RET'
    
    return f"SAV-{prefix}-{compte.id.hex[:8]}-{now.strftime('%Y%m%d%H%M%S')}"


def formater_historique_transaction(transaction: SavingsTransaction) -> dict:
    """
    Formate une transaction pour l'affichage dans l'historique.
    
    Args:
        transaction: Instance SavingsTransaction
        
    Returns:
        dict: Transaction formatée
    """
    return {
        'id': str(transaction.id),
        'date': transaction.date_transaction.strftime('%d/%m/%Y %H:%M'),
        'type': transaction.get_type_transaction_display(),
        'montant': float(transaction.montant),
        'statut': transaction.get_statut_display(),
        'operateur': transaction.get_operateur_display() if transaction.operateur else None,
        'reference': transaction.reference_mobile_money or 'N/A'
    }


# ============================================================================
# HELPERS DE GESTION
# ============================================================================

def obtenir_agents_sfd_pour_validation(sfd) -> list:
    """
    Retourne la liste des agents SFD disponibles pour validation.
    
    Args:
        sfd: Instance SFD
        
    Returns:
        list: Liste des agents disponibles
    """
    return User.objects.filter(
        type_utilisateur=User.TypeUtilisateur.AGENT_SFD,
        sfd=sfd,
        is_active=True
    )


@transaction.atomic
def cloturer_compte_epargne(compte, motif: str, agent) -> dict:
    """
    Clôture un compte épargne et traite le solde restant.
    
    Args:
        compte: Instance SavingsAccount
        motif: Motif de la clôture
        agent: Agent effectuant la clôture
        
    Returns:
        dict: Résultat de la clôture
    """
    if compte.statut == SavingsAccount.StatutChoices.FERME:
        return {'succes': False, 'erreur': 'Le compte est déjà fermé'}
    
    solde = compte.calculer_solde()
    
    # Si il y a un solde, créer une transaction de retrait final
    if solde > 0:
        transaction_retrait = SavingsTransaction.objects.create(
            compte_epargne=compte,
            type_transaction=SavingsTransaction.TypeChoices.RETRAIT,
            montant=solde,
            statut=SavingsTransaction.StatutChoices.EN_ATTENTE,
            numero_telephone=compte.numero_telephone_paiement,  # MIGRATION : numero_mobile_money → numero_telephone
            commentaires=f"Retrait final - Clôture de compte - {motif}"
        )
    
    # Fermer le compte
    compte.statut = SavingsAccount.StatutChoices.FERME
    compte.date_fermeture = timezone.now()
    compte.commentaires_fermeture = motif
    compte.save()
    
    return {
        'succes': True,
        'solde_final': solde,
        'transaction_retrait': transaction_retrait.id if solde > 0 else None
    }


def generer_rapport_compte(compte: SavingsAccount, debut: datetime = None, fin: datetime = None) -> dict:
    """
    Génère un rapport détaillé d'un compte épargne.
    
    Args:
        compte: Instance SavingsAccount
        debut: Date de début de la période
        fin: Date de fin de la période
        
    Returns:
        dict: Rapport du compte
    """
    if not debut:
        debut = compte.date_demande
    if not fin:
        fin = timezone.now()
    
    transactions = compte.transactions.filter(
        date_transaction__range=[debut, fin],
        statut=SavingsTransaction.StatutChoices.CONFIRMEE
    )
    
    stats = calculer_statistiques_compte(compte)
    
    return {
        'compte': {
            'id': str(compte.id),
            'client': compte.client.nom_complet,
            'date_creation': compte.date_demande.strftime('%d/%m/%Y'),
            'statut': compte.get_statut_display(),
            'solde_actuel': stats['solde_actuel']
        },
        'periode': {
            'debut': debut.strftime('%d/%m/%Y'),
            'fin': fin.strftime('%d/%m/%Y')
        },
        'statistiques': stats,
        'transactions': [formater_historique_transaction(t) for t in transactions]
    }
