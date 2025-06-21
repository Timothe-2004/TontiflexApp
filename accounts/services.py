from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from decimal import Decimal
from django.core.files.base import ContentFile
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.contrib.auth.backends import ModelBackend

# --- Backend d'authentification personnalisé ---

class EmailAuthBackend(ModelBackend):
    """
    Authentifie un utilisateur via email + mot de passe (pour tous les types).
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        email = kwargs.get('email', username)
        try:
            user = UserModel.objects.get(email=email)
            if user.check_password(password):
                return user
        except UserModel.DoesNotExist:
            return None
        return None

# --- Fonctions d'inscription pour chaque type d'utilisateur ---

def inscrire_utilisateur(user_type, donnees):
    """
    Inscrit un utilisateur selon le type (client, agent, superviseur, adminSFD, adminPlateforme).
    user_type: str ('client', 'agent', 'superviseur', 'admin_sfd', 'admin_plateforme')
    donnees: dict (données du formulaire)
    """
    from .models import Client, AgentSFD, SuperviseurSFD, AdministrateurSFD, AdminPlateforme
    User = get_user_model()
    # Création du User Django
    user = User.objects.create_user(
        username=donnees['email'],
        email=donnees['email'],
        password=donnees['motDePasse']
    )
    base_kwargs = dict(
        user=user,
        nom=donnees['nom'],
        prenom=donnees['prenom'],
        telephone=donnees['telephone'],
        email=donnees['email'],
        adresse=donnees.get('adresse', ''),
        profession=donnees.get('profession', ''),
        motDePasse=donnees['motDePasse'],
        statut='actif',
    )
    if user_type == 'client':
        base_kwargs.update({
            'pieceIdentite': donnees.get('pieceIdentite'),
            'photoIdentite': donnees.get('photoIdentite'),
            'scorefiabilite': Decimal('0.00')
        })
        return Client.objects.create(**base_kwargs)
    elif user_type == 'agent':
        base_kwargs['sfd'] = donnees.get('sfd')
        return AgentSFD.objects.create(**base_kwargs)
    elif user_type == 'superviseur':
        base_kwargs['sfd'] = donnees.get('sfd')
        return SuperviseurSFD.objects.create(**base_kwargs)
    elif user_type == 'admin_sfd':
        base_kwargs['sfd'] = donnees.get('sfd')
        return AdministrateurSFD.objects.create(**base_kwargs)
    elif user_type == 'admin_plateforme':
        return AdminPlateforme.objects.create(**base_kwargs)
    else:
        raise ValueError('Type utilisateur inconnu')

# --- Fonction de login avec JWT ---
def login_et_jwt(email, mot_de_passe):
    """
    Authentifie un utilisateur (tous types) et retourne un token JWT si succès.
    """
    User = get_user_model()
    try:
        user = User.objects.get(email=email)
        if user.check_password(mot_de_passe):
            refresh = RefreshToken.for_user(user)
            return {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user_id': user.id,
                'email': user.email
            }
        return None
    except User.DoesNotExist:
        return None

def inscrire_client(donnees):
    """
    Inscrit un nouveau client sur la plateforme.
    Args:
        donnees (dict): Données d'inscription (nom, prenom, email, telephone, etc.)
    Returns:
        client (Client) ou None
    """
    try:
        from .models import Client
        # Créer le user Django associé si besoin
        User = get_user_model()
        user = User.objects.create_user(
            username=donnees['email'],
            email=donnees['email'],
            password=donnees['motDePasse']
        )
        client = Client.objects.create(
            user=user,
            nom=donnees['nom'],
            prenom=donnees['prenom'],
            telephone=donnees['telephone'],
            email=donnees['email'],
            adresse=donnees.get('adresse', ''),
            profession=donnees.get('profession', ''),
            motDePasse=donnees['motDePasse'],
            statut=Client.StatutChoices.ACTIF,
            pieceIdentite=donnees.get('pieceIdentite'),
            photoIdentite=donnees.get('photoIdentite'),
            scorefiabilite=Decimal('0.00')
        )
        return client
    except Exception as e:
        return None

def se_connecter(utilisateur, email, mot_de_passe):
    """
    Authentifie un utilisateur avec email et mot de passe.
    Args:
        utilisateur (Utilisateur): instance du modèle Utilisateur
        email (str): Adresse email
        mot_de_passe (str): Mot de passe en clair
    Returns:
        bool: True si authentification réussie, False sinon
    """
    try:
        if utilisateur.email == email and utilisateur.statut == utilisateur.StatutChoices.ACTIF:
            if check_password(mot_de_passe, utilisateur.motDePasse):
                utilisateur.derniere_connexion = timezone.now()
                utilisateur.save(update_fields=['derniere_connexion'])
                return True
        return False
    except Exception:
        return False

def se_deconnecter(utilisateur):
    """
    Déconnecte l'utilisateur (dans une vraie implémentation, cela invaliderait le token JWT).
    """
    # Implémentation à compléter selon la gestion de session/token
    pass

def modifier_profil(utilisateur, donnees):
    """
    Modifie les informations du profil utilisateur.
    Args:
        utilisateur (Utilisateur): instance du modèle Utilisateur
        donnees (dict): Dictionnaire contenant les champs à modifier
    Returns:
        bool: True si modification réussie, False sinon
    """
    try:
        champs_modifiables = [
            'nom', 'prenom', 'telephone', 'email', 'adresse', 'profession'
        ]
        for champ, valeur in donnees.items():
            if champ in champs_modifiables and hasattr(utilisateur, champ):
                setattr(utilisateur, champ, valeur)
        utilisateur.full_clean()
        utilisateur.save()
        return True
    except ValidationError:
        return False
    except Exception:
        return False

def changer_mot_de_passe(utilisateur, ancien_mdp, nouveau_mdp):
    """
    Change le mot de passe de l'utilisateur.
    Args:
        utilisateur (Utilisateur): instance du modèle Utilisateur
        ancien_mdp (str): Ancien mot de passe
        nouveau_mdp (str): Nouveau mot de passe
    Returns:
        bool: True si changement réussi, False sinon
    """
    try:
        if check_password(ancien_mdp, utilisateur.motDePasse):
            utilisateur.motDePasse = make_password(nouveau_mdp)
            utilisateur.save(update_fields=['motDePasse'])
            return True
        return False
    except Exception:
        return False

def valider_email(utilisateur):
    """
    Marque l'email comme vérifié.
    Args:
        utilisateur (Utilisateur): instance du modèle Utilisateur
    Returns:
        bool: True si validation réussie, False sinon
    """
    try:
        utilisateur.email_verifie = True
        utilisateur.save(update_fields=['email_verifie'])
        return True
    except Exception:
        return False

# --- Services pour AdministrateurSFD ---

def tontines_gerees(administrateur):
    """
    Retourne le nombre de tontines gérées par cet administrateur.
    """
    from tontines.models import Tontine
    return Tontine.objects.filter(administrateur=administrateur).count()

def creer_tontine(administrateur, nom, description, montant_mise, nombre_participants_max, duree_cycle, type_tontine='tournante'):
    """
    Crée une nouvelle tontine.
    """
    try:
        if not administrateur.peut_creer_tontines:
            raise ValueError("Vous n'avez pas l'autorisation de créer des tontines")
        from tontines.models import Tontine
        tontine = Tontine.objects.create(
            nom=nom,
            description=description,
            montant_mise=montant_mise,
            nombre_participants_max=nombre_participants_max,
            duree_cycle=duree_cycle,
            type_tontine=type_tontine,
            administrateur=administrateur,
            statut='en_formation',
            date_creation=timezone.now()
        )
        return tontine
    except Exception as e:
        print(f"Erreur lors de la création de la tontine: {e}")
        return None

def configurer_tontine(administrateur, tontine, configuration):
    """
    Configure les paramètres d'une tontine existante.
    """
    try:
        if tontine.administrateur != administrateur:
            raise ValueError("Vous n'administrez pas cette tontine")
        if tontine.statut != 'en_formation':
            raise ValueError("La tontine ne peut plus être configurée")
        for param, valeur in configuration.items():
            if hasattr(tontine, param):
                setattr(tontine, param, valeur)
        if not tontine.historique_configuration:
            tontine.historique_configuration = {}
        tontine.historique_configuration[timezone.now().isoformat()] = {
            'administrateur': f"{administrateur.nom} {administrateur.prenom}",
            'configuration': configuration
        }
        tontine.save()
        return True
    except Exception as e:
        print(f"Erreur lors de la configuration: {e}")
        return False

def valider_pret(administrateur, demande_pret, conditions_administrateur=None):
    """
    Valide un prêt en tant qu'administrateur (pour les montants importants).
    """
    try:
        if not administrateur.peut_valider_gros_prets:
            raise ValueError("Vous n'avez pas l'autorisation de valider les prêts")
        montant_demande = demande_pret.formulaire.montant_demande
        if montant_demande > administrateur.montant_max_gestion:
            raise ValueError(
                f"Montant {montant_demande} dépasse votre autorisation maximale "
                f"de {administrateur.montant_max_gestion}"
            )
        if demande_pret.statut != 'en_attente_validation_admin':
            raise ValueError("Cette demande ne nécessite pas de validation administrateur")
        validation_finale = effectuer_validation_finale(administrateur, demande_pret)
        if validation_finale['valide']:
            return demande_pret.approuver(
                administrateur=administrateur,
                conditions_speciales=conditions_administrateur
            )
        else:
            return demande_pret.rejeter(
                validation_finale['motifs'],
                administrateur=administrateur
            )
    except Exception as e:
        print(f"Erreur lors de la validation: {e}")
        return False

def effectuer_validation_finale(administrateur, demande_pret):
    """
    Effectue une validation finale approfondie d'une demande de prêt.
    """
    motifs_rejet = []
    if demande_pret.score_final < 80:
        motifs_rejet.append("Score de fiabilité insuffisant pour un gros prêt")
    capacite = demande_pret.formulaire.calculer_capacite_remboursement()
    if capacite < demande_pret.formulaire.montant_demande * 0.3:
        motifs_rejet.append("Capacité de remboursement insuffisante")
    if demande_pret.formulaire.montant_demande > 5000000:
        if not demande_pret.formulaire.garantie_immobiliere and not demande_pret.formulaire.garantie_vehicule:
            motifs_rejet.append("Garanties insuffisantes pour ce montant")
    return {
        'valide': len(motifs_rejet) == 0,
        'motifs': '; '.join(motifs_rejet) if motifs_rejet else None
    }

def suspendre_tontine(administrateur, tontine, motif):
    """
    Suspend une tontine avec un motif.
    """
    try:
        if tontine.administrateur != administrateur:
            raise ValueError("Vous n'administrez pas cette tontine")
        tontine.statut = 'suspendue'
        tontine.motif_suspension = motif
        tontine.date_suspension = timezone.now()
        tontine.administrateur_suspension = administrateur
        tontine.save()
        return True
    except Exception as e:
        print(f"Erreur lors de la suspension: {e}")
        return False

def cloturer_tontine(administrateur, tontine):
    """
    Clôture une tontine arrivée à terme.
    """
    try:
        if tontine.administrateur != administrateur:
            raise ValueError("Vous n'administrez pas cette tontine")
        if not tontine.peut_etre_cloturee():
            raise ValueError("La tontine ne peut pas encore être clôturée")
        resultat_cloture = tontine.cloturer()
        if resultat_cloture:
            mettre_a_jour_statistiques_tontine(administrateur, 'cloture', tontine)
        return resultat_cloture
    except Exception as e:
        print(f"Erreur lors de la clôture: {e}")
        return False

def obtenir_tontines_administrees(administrateur, statut=None):
    """
    Retourne toutes les tontines administrées par cet administrateur.
    """
    from tontines.models import Tontine
    queryset = Tontine.objects.filter(administrateur=administrateur)
    if statut:
        queryset = queryset.filter(statut=statut)
    return queryset.order_by('-date_creation')

def generer_rapport_administration(administrateur, date_debut=None, date_fin=None):
    """
    Génère un rapport d'administration sur une période donnée.
    """
    if not date_debut:
        date_debut = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if not date_fin:
        date_fin = timezone.now()
    tontines = obtenir_tontines_administrees(administrateur)
    tontines_periode = tontines.filter(
        date_creation__gte=date_debut,
        date_creation__lte=date_fin
    )
    from demandes.models import DemandePret
    prets_valides = DemandePret.objects.filter(
        administrateur_validation=administrateur,
        date_approbation__gte=date_debut,
        date_approbation__lte=date_fin
    )
    rapport = {
        'administrateur': f"{administrateur.nom} {administrateur.prenom}",
        'sfd_id': administrateur.sfd_id,
        'periode': {
            'debut': date_debut.isoformat(),
            'fin': date_fin.isoformat()
        },
        'tontines': {
            'total_administrees': tontines.count(),
            'creees_periode': tontines_periode.count(),
            'actives': tontines.filter(statut='active').count(),
            'en_formation': tontines.filter(statut='en_formation').count(),
            'clôturees': tontines.filter(statut='clôturée').count(),
            'suspendues': tontines.filter(statut='suspendue').count()
        },
        'prets': {
            'valides_periode': prets_valides.count(),
            'montant_total_valide': float(
                prets_valides.aggregate(
                    total=Sum('formulaire__montant_demande')
                )['total'] or 0
            )
        },
        'performance': {
            'taux_reussite_tontines': 0,
            'montant_moyen_pret': 0
        }
    }
    if rapport['tontines']['total_administrees'] > 0:
        tontines_reussies = tontines.filter(
            statut__in=['clôturée', 'active']
        ).count()
        rapport['performance']['taux_reussite_tontines'] = round(
            (tontines_reussies / rapport['tontines']['total_administrees']) * 100,
            2
        )
    if rapport['prets']['valides_periode'] > 0:
        rapport['performance']['montant_moyen_pret'] = round(
            rapport['prets']['montant_total_valide'] / rapport['prets']['valides_periode'],
            2
        )
    return rapport

def mettre_a_jour_statistiques_tontine(administrateur, action, tontine):
    """
    Met à jour les statistiques liées aux actions sur les tontines.
    """
    if hasattr(administrateur, 'statistiques') and administrateur.statistiques:
        administrateur.statistiques.mettre_a_jour()

# --- Fin services AdministrateurSFD ---

# --- Synchronisation User Django <-> profils métiers ---
def get_profile_for_user(user):
    """
    Retourne l'instance métier (Client, AgentSFD, etc.) liée à un User Django.
    """
    from .models import Client, AgentSFD, SuperviseurSFD, AdministrateurSFD, AdminPlateforme
    for model in [Client, AgentSFD, SuperviseurSFD, AdministrateurSFD, AdminPlateforme]:
        try:
            return model.objects.get(user=user)
        except model.DoesNotExist:
            continue
    return None
