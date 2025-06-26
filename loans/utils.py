"""
UTILITAIRES POUR LE MODULE PRÊTS - TONTIFLEX

Ce module contient toutes les fonctions utilitaires pour:
1. Calculs d'échéances et mensualités
2. Calculs de pénalités
3. Score de fiabilité automatique
4. Génération de rapports
5. Notifications automatiques

Fonctions critiques pour le workflow des prêts
"""

import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta, date
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


# =============================================================================
# CALCULS FINANCIERS
# =============================================================================

def calculer_mensualite(montant_principal, taux_annuel, duree_mois):
    """
    Calcule la mensualité d'un prêt avec la formule d'annuité constante.
    
    Args:
        montant_principal (Decimal): Montant du prêt
        taux_annuel (Decimal): Taux d'intérêt annuel en pourcentage
        duree_mois (int): Durée du prêt en mois
        
    Returns:
        Decimal: Mensualité calculée
    """
    try:
        montant = Decimal(str(montant_principal))
        taux_mensuel = Decimal(str(taux_annuel)) / Decimal('12') / Decimal('100')
        duree = int(duree_mois)
        
        if taux_mensuel == 0:
            # Prêt à taux zéro
            return montant / Decimal(str(duree))
        
        # Formule d'annuité constante
        coefficient = (taux_mensuel * (1 + taux_mensuel) ** duree) / \
                     ((1 + taux_mensuel) ** duree - 1)
        
        mensualite = montant * coefficient
        
        # Arrondir à 2 décimales
        return mensualite.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
    except Exception as e:
        logger.error(f"Erreur calcul mensualité: {e}")
        raise ValidationError(f"Erreur dans le calcul de la mensualité: {e}")


def calculer_tableau_amortissement(montant_principal, taux_annuel, duree_mois, date_debut):
    """
    Génère le tableau d'amortissement complet d'un prêt.
    
    Args:
        montant_principal (Decimal): Montant du prêt
        taux_annuel (Decimal): Taux d'intérêt annuel
        duree_mois (int): Durée en mois
        date_debut (date): Date de première échéance
        
    Returns:
        list: Liste des échéances avec détails
    """
    try:
        mensualite = calculer_mensualite(montant_principal, taux_annuel, duree_mois)
        taux_mensuel = Decimal(str(taux_annuel)) / Decimal('12') / Decimal('100')
        solde_restant = Decimal(str(montant_principal))
        
        tableau = []
        
        for i in range(duree_mois):
            # Calcul des intérêts pour cette période
            interet = solde_restant * taux_mensuel
            interet = interet.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Calcul du capital remboursé
            capital = mensualite - interet
            capital = capital.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Nouveau solde
            solde_restant -= capital
            solde_restant = max(solde_restant, Decimal('0.00'))
            
            # Date d'échéance
            date_echeance = calculer_date_echeance(date_debut, i)
            
            tableau.append({
                'numero': i + 1,
                'date_echeance': date_echeance,
                'mensualite': mensualite,
                'capital': capital,
                'interet': interet,
                'solde_restant': solde_restant
            })
        
        return tableau
        
    except Exception as e:
        logger.error(f"Erreur tableau amortissement: {e}")
        raise ValidationError(f"Erreur dans le calcul du tableau d'amortissement: {e}")


def calculer_date_echeance(date_premiere, nombre_mois):
    """
    Calcule la date d'échéance en ajoutant des mois à la date de première échéance.
    
    Args:
        date_premiere (date): Date de première échéance
        nombre_mois (int): Nombre de mois à ajouter
        
    Returns:
        date: Date d'échéance calculée
    """
    try:
        annee = date_premiere.year
        mois = date_premiere.month + nombre_mois
        jour = date_premiere.day
        
        # Gérer le dépassement d'année
        while mois > 12:
            mois -= 12
            annee += 1
        
        # Gérer les mois avec moins de jours
        try:
            return date(annee, mois, jour)
        except ValueError:
            # Si le jour n'existe pas dans ce mois (ex: 31/02), prendre le dernier jour du mois
            if mois == 2:
                # Février
                if (annee % 4 == 0 and annee % 100 != 0) or (annee % 400 == 0):
                    return date(annee, mois, 29)  # Année bissextile
                else:
                    return date(annee, mois, 28)
            elif mois in [4, 6, 9, 11]:
                return date(annee, mois, 30)
            else:
                return date(annee, mois, 31)
                
    except Exception as e:
        logger.error(f"Erreur calcul date échéance: {e}")
        return date_premiere


def calculer_penalites_retard(montant_mensualite, taux_penalite_quotidien, jours_retard):
    """
    Calcule les pénalités de retard selon le taux quotidien.
    
    Args:
        montant_mensualite (Decimal): Montant de la mensualité
        taux_penalite_quotidien (Decimal): Taux de pénalité par jour en %
        jours_retard (int): Nombre de jours de retard
        
    Returns:
        Decimal: Montant des pénalités
    """
    try:
        if jours_retard <= 0:
            return Decimal('0.00')
        
        mensualite = Decimal(str(montant_mensualite))
        taux_quotidien = Decimal(str(taux_penalite_quotidien)) / Decimal('100')
        jours = Decimal(str(jours_retard))
        
        penalites = mensualite * taux_quotidien * jours
        
        return penalites.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
    except Exception as e:
        logger.error(f"Erreur calcul pénalités: {e}")
        return Decimal('0.00')


def calculer_cout_total_pret(montant_principal, mensualite, duree_mois):
    """
    Calcule le coût total d'un prêt (capital + intérêts).
    
    Args:
        montant_principal (Decimal): Montant emprunté
        mensualite (Decimal): Mensualité
        duree_mois (int): Durée en mois
        
    Returns:
        dict: Coût total et détails
    """
    try:
        principal = Decimal(str(montant_principal))
        total_rembourse = Decimal(str(mensualite)) * Decimal(str(duree_mois))
        cout_interet = total_rembourse - principal
        
        return {
            'montant_principal': principal,
            'total_rembourse': total_rembourse,
            'cout_interet': cout_interet,
            'taux_effectif': (cout_interet / principal) * Decimal('100') if principal > 0 else Decimal('0')
        }
        
    except Exception as e:
        logger.error(f"Erreur calcul coût total: {e}")
        return {}


# =============================================================================
# SCORE DE FIABILITÉ
# =============================================================================

def calculer_score_fiabilite_client(client):
    """
    Calcule le score de fiabilité d'un client selon plusieurs critères.
    
    Args:
        client: Instance du modèle Client
        
    Returns:
        dict: Score et détails du calcul
    """
    try:
        score = Decimal('50.00')  # Score de base
        details = {
            'score_base': 50.00,
            'bonus_anciennete_epargne': 0.00,
            'bonus_participation_tontines': 0.00,
            'bonus_regularite_cotisations': 0.00,
            'bonus_historique_prets': 0.00,
            'malus_retards': 0.00
        }
        
        # 1. Bonus ancienneté compte épargne (max 20 points)
        if hasattr(client, 'compte_epargne') and client.compte_epargne.statut == 'actif':
            anciennete_jours = (timezone.now() - client.compte_epargne.date_activation).days
            anciennete_mois = anciennete_jours / 30
            bonus_anciennete = min(Decimal('20.00'), Decimal(str(anciennete_mois * 2)))
            score += bonus_anciennete
            details['bonus_anciennete_epargne'] = float(bonus_anciennete)
        
        # 2. Bonus participation aux tontines (max 15 points)
        try:
            tontines_actives = client.tontines_participees.filter(statut='actif').count()
            bonus_tontines = min(Decimal('15.00'), Decimal(str(tontines_actives * 5)))
            score += bonus_tontines
            details['bonus_participation_tontines'] = float(bonus_tontines)
        except:
            pass
        
        # 3. Bonus régularité des cotisations (max 15 points)
        try:
            # Calculer le taux de ponctualité des cotisations
            total_cotisations = client.cotisations.count()
            if total_cotisations > 0:
                cotisations_a_temps = client.cotisations.filter(
                    date_cotisation__lte=timezone.now()
                ).count()
                taux_ponctualite = (cotisations_a_temps / total_cotisations) * 100
                bonus_regularite = min(Decimal('15.00'), Decimal(str(taux_ponctualite * 0.15)))
                score += bonus_regularite
                details['bonus_regularite_cotisations'] = float(bonus_regularite)
        except:
            pass
        
        # 4. Historique des prêts antérieurs (max 10 points, min -20 points)
        try:
            prets_anterieurs = client.prets.exclude(statut='accorde')
            if prets_anterieurs.exists():
                prets_soldes = prets_anterieurs.filter(statut='solde').count()
                prets_defaut = prets_anterieurs.filter(statut='en_defaut').count()
                
                if prets_soldes > 0 and prets_defaut == 0:
                    bonus_historique = min(Decimal('10.00'), Decimal(str(prets_soldes * 5)))
                    score += bonus_historique
                    details['bonus_historique_prets'] = float(bonus_historique)
                elif prets_defaut > 0:
                    malus_defaut = min(Decimal('20.00'), Decimal(str(prets_defaut * 10)))
                    score -= malus_defaut
                    details['malus_retards'] = float(malus_defaut)
        except:
            pass
        
        # 5. Pénalités pour retards récents (max -10 points)
        try:
            # Vérifier les retards dans les 6 derniers mois
            date_limite = timezone.now() - timedelta(days=180)
            retards_recents = 0
            
            # Retards sur cotisations tontines
            try:
                retards_tontines = client.cotisations.filter(
                    date_cotisation__gte=date_limite,
                    # Ajouter condition retard si disponible
                ).count()
                retards_recents += retards_tontines
            except:
                pass
            
            # Retards sur remboursements prêts
            try:
                echeances_retard = client.prets.filter(
                    echeances__date_echeance__gte=date_limite,
                    echeances__statut='en_retard'
                ).count()
                retards_recents += echeances_retard
            except:
                pass
            
            if retards_recents > 0:
                malus_retards = min(Decimal('10.00'), Decimal(str(retards_recents * 2)))
                score -= malus_retards
                details['malus_retards'] += float(malus_retards)
        except:
            pass
        
        # Score final entre 0 et 100
        score_final = max(Decimal('0.00'), min(score, Decimal('100.00')))
        
        return {
            'score': float(score_final),
            'details': details,
            'evaluation': evaluer_score_fiabilite(score_final),
            'recommandations': generer_recommandations_score(score_final, details)
        }
        
    except Exception as e:
        logger.error(f"Erreur calcul score fiabilité: {e}")
        return {
            'score': 0.00,
            'details': {},
            'evaluation': 'Erreur de calcul',
            'recommandations': []
        }


def evaluer_score_fiabilite(score):
    """
    Évalue la qualité d'un score de fiabilité.
    
    Args:
        score (Decimal): Score entre 0 et 100
        
    Returns:
        str: Évaluation textuelle
    """
    score_float = float(score)
    
    if score_float >= 85:
        return "Excellent - Très faible risque"
    elif score_float >= 70:
        return "Bon - Risque faible"
    elif score_float >= 55:
        return "Moyen - Risque modéré"
    elif score_float >= 40:
        return "Faible - Risque élevé"
    else:
        return "Très faible - Risque très élevé"


def generer_recommandations_score(score, details):
    """
    Génère des recommandations basées sur le score et ses composants.
    
    Args:
        score (Decimal): Score de fiabilité
        details (dict): Détails du calcul
        
    Returns:
        list: Liste de recommandations
    """
    recommandations = []
    score_float = float(score)
    
    if score_float < 55:
        recommandations.append("Score insuffisant - Prêt non recommandé sans garanties supplémentaires")
    
    if details.get('bonus_anciennete_epargne', 0) < 10:
        recommandations.append("Compte épargne récent - Encourager l'épargne régulière")
    
    if details.get('bonus_participation_tontines', 0) < 5:
        recommandations.append("Faible participation aux tontines - Proposer adhésion")
    
    if details.get('malus_retards', 0) > 0:
        recommandations.append("Historique de retards - Suivi renforcé recommandé")
    
    if score_float >= 70:
        recommandations.append("Profil fiable - Prêt recommandé")
    
    return recommandations


# =============================================================================
# ANALYSES ET RAPPORTS
# =============================================================================

def analyser_capacite_remboursement(revenu_mensuel, charges_mensuelles, mensualite_pret):
    """
    Analyse la capacité de remboursement d'un client.
    
    Args:
        revenu_mensuel (Decimal): Revenus mensuels
        charges_mensuelles (Decimal): Charges mensuelles
        mensualite_pret (Decimal): Mensualité du prêt demandé
        
    Returns:
        dict: Analyse détaillée
    """
    try:
        revenu = Decimal(str(revenu_mensuel))
        charges = Decimal(str(charges_mensuelles))
        mensualite = Decimal(str(mensualite_pret))
        
        reste_a_vivre = revenu - charges
        ratio_endettement = ((charges + mensualite) / revenu) * 100 if revenu > 0 else 0
        reste_apres_pret = reste_a_vivre - mensualite
        
        # Seuils recommandés
        ratio_max_recommande = 33  # 33% maximum recommandé
        reste_minimum = revenu * Decimal('0.30')  # 30% minimum pour vivre
        
        analyse = {
            'revenu_mensuel': float(revenu),
            'charges_actuelles': float(charges),
            'reste_a_vivre_actuel': float(reste_a_vivre),
            'mensualite_pret': float(mensualite),
            'nouveau_ratio_endettement': float(ratio_endettement),
            'reste_apres_pret': float(reste_apres_pret),
            'ratio_max_recommande': ratio_max_recommande,
            'reste_minimum_recommande': float(reste_minimum),
            'analyse_favorable': False,
            'niveau_risque': 'Élevé',
            'commentaires': []
        }
        
        # Évaluation
        if ratio_endettement <= ratio_max_recommande and reste_apres_pret >= reste_minimum:
            analyse['analyse_favorable'] = True
            analyse['niveau_risque'] = 'Faible'
            analyse['commentaires'].append("Capacité de remboursement suffisante")
        elif ratio_endettement <= 40 and reste_apres_pret >= reste_minimum * Decimal('0.8'):
            analyse['niveau_risque'] = 'Modéré'
            analyse['commentaires'].append("Capacité limite - Suivi recommandé")
        else:
            analyse['commentaires'].append("Capacité insuffisante - Prêt non recommandé")
        
        if ratio_endettement > ratio_max_recommande:
            analyse['commentaires'].append(f"Taux d'endettement trop élevé ({ratio_endettement:.1f}% > {ratio_max_recommande}%)")
        
        if reste_apres_pret < reste_minimum:
            analyse['commentaires'].append("Reste à vivre insuffisant après remboursement")
        
        return analyse
        
    except Exception as e:
        logger.error(f"Erreur analyse capacité: {e}")
        return {'erreur': str(e)}


def generer_rapport_demande(demande):
    """
    Génère un rapport complet sur une demande de prêt.
    
    Args:
        demande: Instance de LoanApplication
        
    Returns:
        dict: Rapport détaillé
    """
    try:
        rapport = {
            'demande_id': str(demande.id),
            'client': {
                'nom': demande.client.nom_complet,
                'age': demande.age_demandeur if hasattr(demande, 'age_demandeur') else None,
                'situation_familiale': demande.situation_familiale,
                'profession': demande.situation_professionnelle
            },
            'pret_demande': {
                'montant': float(demande.montant_souhaite),
                'duree': demande.duree_pret,
                'type': demande.type_pret,
                'objet': demande.objet_pret
            },
            'situation_financiere': {
                'revenu_mensuel': float(demande.revenu_mensuel),
                'charges_mensuelles': float(demande.charges_mensuelles),
                'ratio_endettement': float(demande.ratio_endettement)
            },
            'score_fiabilite': None,
            'analyse_capacite': None,
            'recommandations': [],
            'niveau_risque_global': 'Non évalué',
            'decision_recommandee': 'En attente d\'analyse'
        }
        
        # Calcul du score de fiabilité
        score_info = calculer_score_fiabilite_client(demande.client)
        rapport['score_fiabilite'] = score_info
        
        # Analyse de capacité si conditions définies
        if hasattr(demande, 'conditions_remboursement'):
            conditions = demande.conditions_remboursement
            analyse_capacite = analyser_capacite_remboursement(
                demande.revenu_mensuel,
                demande.charges_mensuelles,
                conditions.montant_mensualite
            )
            rapport['analyse_capacite'] = analyse_capacite
        
        # Recommandation globale
        score = score_info.get('score', 0)
        if score >= 70 and rapport['analyse_capacite'] and rapport['analyse_capacite'].get('analyse_favorable'):
            rapport['niveau_risque_global'] = 'Faible'
            rapport['decision_recommandee'] = 'Prêt recommandé'
        elif score >= 55:
            rapport['niveau_risque_global'] = 'Modéré'
            rapport['decision_recommandee'] = 'Prêt possible avec conditions'
        else:
            rapport['niveau_risque_global'] = 'Élevé'
            rapport['decision_recommandee'] = 'Prêt non recommandé'
        
        return rapport
        
    except Exception as e:
        logger.error(f"Erreur génération rapport: {e}")
        return {'erreur': str(e)}


# =============================================================================
# STATISTIQUES
# =============================================================================

def calculer_statistiques_prets(sfd=None, periode_mois=12):
    """
    Calcule les statistiques des prêts pour un SFD ou globalement.
    
    Args:
        sfd: Instance SFD (optionnel)
        periode_mois (int): Période d'analyse en mois
        
    Returns:
        dict: Statistiques détaillées
    """
    try:
        from .models import LoanApplication, Loan, Payment
        
        # Filtrage par SFD si spécifié
        if sfd:
            # Filtrer via les clients ayant un compte épargne de cette SFD
            demandes = LoanApplication.objects.filter(
                client__compte_epargne__agent_validateur__sfd=sfd
            )
            prets = Loan.objects.filter(
                client__compte_epargne__agent_validateur__sfd=sfd
            )
        else:
            demandes = LoanApplication.objects.all()
            prets = Loan.objects.all()
        
        # Période d'analyse
        date_debut = timezone.now() - timedelta(days=periode_mois * 30)
        
        stats = {
            'periode': f"Derniers {periode_mois} mois",
            'demandes': {
                'total': demandes.count(),
                'nouvelles_periode': demandes.filter(date_soumission__gte=date_debut).count(),
                'en_attente': demandes.filter(statut='soumis').count(),
                'en_examen': demandes.filter(statut='en_cours_examen').count(),
                'transferees': demandes.filter(statut='transfere_admin').count(),
                'accordees': demandes.filter(statut='accorde').count(),
                'rejetees': demandes.filter(statut='rejete').count()
            },
            'prets': {
                'total_accorde': prets.count(),
                'en_attente_decaissement': prets.filter(statut='accorde').count(),
                'decaisses': prets.filter(statut='decaisse').count(),
                'en_remboursement': prets.filter(statut='en_remboursement').count(),
                'soldes': prets.filter(statut='solde').count(),
                'en_defaut': prets.filter(statut='en_defaut').count()
            },
            'montants': {
                'total_demande': float(demandes.aggregate(Sum('montant_souhaite'))['montant_souhaite__sum'] or 0),
                'total_accorde': float(prets.aggregate(Sum('montant_accorde'))['montant_accorde__sum'] or 0),
                'montant_moyen_demande': float(demandes.aggregate(Avg('montant_souhaite'))['montant_souhaite__avg'] or 0),
                'montant_moyen_accorde': float(prets.aggregate(Avg('montant_accorde'))['montant_accorde__avg'] or 0)
            },
            'taux': {
                'approbation': 0,
                'rejet': 0,
                'defaut': 0
            }
        }
        
        # Calcul des taux
        total_traitees = stats['demandes']['accordees'] + stats['demandes']['rejetees']
        if total_traitees > 0:
            stats['taux']['approbation'] = (stats['demandes']['accordees'] / total_traitees) * 100
            stats['taux']['rejet'] = (stats['demandes']['rejetees'] / total_traitees) * 100
        
        total_prets = stats['prets']['total_accorde']
        if total_prets > 0:
            stats['taux']['defaut'] = (stats['prets']['en_defaut'] / total_prets) * 100
        
        return stats
        
    except Exception as e:
        logger.error(f"Erreur calcul statistiques: {e}")
        return {'erreur': str(e)}


# =============================================================================
# UTILITAIRES DIVERS
# =============================================================================

def formater_montant(montant, devise='FCFA'):
    """
    Formate un montant pour l'affichage.
    
    Args:
        montant: Montant à formater
        devise (str): Devise à afficher
        
    Returns:
        str: Montant formaté
    """
    try:
        if isinstance(montant, (int, float, Decimal)):
            return f"{montant:,.0f} {devise}".replace(',', ' ')
        return f"0 {devise}"
    except:
        return f"0 {devise}"


def valider_document_pdf(document):
    """
    Valide qu'un document est bien un PDF valide.
    
    Args:
        document: Fichier à valider
        
    Returns:
        dict: Résultat de validation
    """
    try:
        if not document:
            return {'valid': False, 'erreur': 'Aucun document fourni'}
        
        # Vérifier l'extension
        if not document.name.lower().endswith('.pdf'):
            return {'valid': False, 'erreur': 'Le document doit être un fichier PDF'}
        
        # Vérifier la taille (max 10MB)
        if document.size > 10 * 1024 * 1024:
            return {'valid': False, 'erreur': 'Le document ne doit pas dépasser 10 MB'}
        
        # Vérifier le contenu (début du fichier PDF)
        document.seek(0)
        header = document.read(5)
        document.seek(0)
        
        if header != b'%PDF-':
            return {'valid': False, 'erreur': 'Le fichier n\'est pas un PDF valide'}
        
        return {'valid': True, 'message': 'Document PDF valide'}
        
    except Exception as e:
        return {'valid': False, 'erreur': f'Erreur de validation: {str(e)}'}


def generer_reference_unique(prefix='LOAN'):
    """
    Génère une référence unique pour les prêts.
    
    Args:
        prefix (str): Préfixe de la référence
        
    Returns:
        str: Référence unique
    """
    import random
    import string
    
    timestamp = int(timezone.now().timestamp())
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    return f"{prefix}_{timestamp}_{random_str}"


def convertir_duree_lisible(duree_mois):
    """
    Convertit une durée en mois en format lisible.
    
    Args:
        duree_mois (int): Durée en mois
        
    Returns:
        str: Durée formatée
    """
    if duree_mois < 12:
        return f"{duree_mois} mois"
    elif duree_mois % 12 == 0:
        annees = duree_mois // 12
        return f"{annees} {'an' if annees == 1 else 'ans'}"
    else:
        annees = duree_mois // 12
        mois_restants = duree_mois % 12
        return f"{annees} {'an' if annees == 1 else 'ans'} et {mois_restants} mois"
