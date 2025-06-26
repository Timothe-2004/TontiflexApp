"""
PERMISSIONS PERSONNALISÉES POUR LE MODULE PRÊTS - TONTIFLEX

Ce module définit les permissions spécifiques au workflow des prêts:
1. Client: demander, consulter ses prêts, rembourser
2. Superviseur SFD: examiner, définir conditions, transférer
3. Admin SFD: validation finale, décaissement
4. Admin Plateforme: accès complet

Respecte les règles métier du workflow obligatoire Superviseur → Admin
"""

from rest_framework.permissions import BasePermission
from django.core.exceptions import ObjectDoesNotExist


class IsClientOwner(BasePermission):
    """
    Permission pour les clients - accès uniquement à leurs propres demandes/prêts
    """
    
    def has_permission(self, request, view):
        # L'utilisateur doit être authentifié et être un client
        return (request.user.is_authenticated and 
                hasattr(request.user, 'client'))
    
    def has_object_permission(self, request, view, obj):
        # Vérifier que l'objet appartient au client
        if hasattr(obj, 'client'):
            return obj.client.user == request.user
        elif hasattr(obj, 'loan') and hasattr(obj.loan, 'client'):
            return obj.loan.client.user == request.user
        elif hasattr(obj, 'demande') and hasattr(obj.demande, 'client'):
            return obj.demande.client.user == request.user
        return False


class IsSuperviseurSFD(BasePermission):
    """
    Permission pour les superviseurs SFD - examiner et traiter les demandes
    """
    
    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                hasattr(request.user, 'superviseurssfd'))
    
    def has_object_permission(self, request, view, obj):
        # Superviseur peut accéder aux demandes de sa SFD
        try:
            user_sfd = request.user.superviseurssfd.sfd
            
            # Pour les demandes de prêt
            if hasattr(obj, 'client'):
                # Vérifier si le client appartient à la même SFD via son compte épargne
                if hasattr(obj.client, 'compte_epargne'):
                    return obj.client.compte_epargne.agent_validateur.sfd == user_sfd
            
            # Pour les objets liés (loan, conditions, etc.)
            elif hasattr(obj, 'demande'):
                if hasattr(obj.demande.client, 'compte_epargne'):
                    return obj.demande.client.compte_epargne.agent_validateur.sfd == user_sfd
            
            return False
        except (ObjectDoesNotExist, AttributeError):
            return False


class IsAdminSFD(BasePermission):
    """
    Permission pour les administrateurs SFD - validation finale et décaissement
    """
    
    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                hasattr(request.user, 'administrateurssfd'))
    
    def has_object_permission(self, request, view, obj):
        # Admin SFD peut accéder aux demandes transférées de sa SFD
        try:
            user_sfd = request.user.administrateurssfd.sfd
            
            # Pour les demandes de prêt
            if hasattr(obj, 'client'):
                if hasattr(obj.client, 'compte_epargne'):
                    return obj.client.compte_epargne.agent_validateur.sfd == user_sfd
            
            # Pour les objets liés
            elif hasattr(obj, 'demande'):
                if hasattr(obj.demande.client, 'compte_epargne'):
                    return obj.demande.client.compte_epargne.agent_validateur.sfd == user_sfd
            
            return False
        except (ObjectDoesNotExist, AttributeError):
            return False


class IsAdminPlateforme(BasePermission):
    """
    Permission pour l'admin plateforme - accès complet à tout
    """
    
    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                hasattr(request.user, 'adminplateforme'))
    
    def has_object_permission(self, request, view, obj):
        # Admin plateforme a accès à tout
        return True


class CanExamineLoanApplication(BasePermission):
    """
    Permission spécifique pour examiner une demande de prêt
    Seuls les superviseurs SFD de la bonne SFD peuvent examiner
    """
    
    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                (hasattr(request.user, 'superviseurssfd') or 
                 hasattr(request.user, 'adminplateforme')))
    
    def has_object_permission(self, request, view, obj):
        # Admin plateforme peut tout faire
        if hasattr(request.user, 'adminplateforme'):
            return True
        
        # Superviseur doit être de la bonne SFD et demande doit être examinable
        if hasattr(request.user, 'superviseurssfd'):
            try:
                user_sfd = request.user.superviseurssfd.sfd
                
                # Vérifier SFD
                if hasattr(obj.client, 'compte_epargne'):
                    client_sfd = obj.client.compte_epargne.agent_validateur.sfd
                    if client_sfd != user_sfd:
                        return False
                
                # Vérifier que la demande peut être examinée
                return obj.peut_etre_examinee
            except (ObjectDoesNotExist, AttributeError):
                return False
        
        return False


class CanDefineTerms(BasePermission):
    """
    Permission pour définir les conditions de remboursement
    Seul le superviseur qui a examiné la demande peut définir les conditions
    """
    
    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                (hasattr(request.user, 'superviseurssfd') or 
                 hasattr(request.user, 'adminplateforme')))
    
    def has_object_permission(self, request, view, obj):
        # Admin plateforme peut tout faire
        if hasattr(request.user, 'adminplateforme'):
            return True
        
        # Vérifier que c'est le superviseur examinateur
        if hasattr(request.user, 'superviseurssfd'):
            return (obj.statut == 'en_cours_examen' and 
                    obj.superviseur_examinateur == request.user.superviseurssfd)
        
        return False


class CanTransferToAdmin(BasePermission):
    """
    Permission pour transférer à l'admin
    Seul le superviseur examinateur avec conditions définies peut transférer
    """
    
    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                (hasattr(request.user, 'superviseurssfd') or 
                 hasattr(request.user, 'adminplateforme')))
    
    def has_object_permission(self, request, view, obj):
        # Admin plateforme peut tout faire
        if hasattr(request.user, 'adminplateforme'):
            return True
        
        # Vérifier conditions de transfert
        if hasattr(request.user, 'superviseurssfd'):
            return (obj.superviseur_examinateur == request.user.superviseurssfd and
                    obj.peut_etre_transferee)
        
        return False


class CanFinalApprove(BasePermission):
    """
    Permission pour la validation finale
    Seuls les admins SFD peuvent valider définitivement
    """
    
    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                (hasattr(request.user, 'administrateurssfd') or 
                 hasattr(request.user, 'adminplateforme')))
    
    def has_object_permission(self, request, view, obj):
        # Admin plateforme peut tout faire
        if hasattr(request.user, 'adminplateforme'):
            return True
        
        # Admin SFD de la bonne SFD et demande transférée
        if hasattr(request.user, 'administrateurssfd'):
            try:
                user_sfd = request.user.administrateurssfd.sfd
                
                # Vérifier SFD
                if hasattr(obj.client, 'compte_epargne'):
                    client_sfd = obj.client.compte_epargne.agent_validateur.sfd
                    if client_sfd != user_sfd:
                        return False
                
                # Vérifier que la demande peut être validée
                return obj.peut_etre_validee
            except (ObjectDoesNotExist, AttributeError):
                return False
        
        return False


class CanMarkDisbursed(BasePermission):
    """
    Permission pour marquer comme décaissé
    Seuls les admins SFD peuvent marquer les décaissements
    """
    
    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                (hasattr(request.user, 'administrateurssfd') or 
                 hasattr(request.user, 'adminplateforme')))
    
    def has_object_permission(self, request, view, obj):
        # Admin plateforme peut tout faire
        if hasattr(request.user, 'adminplateforme'):
            return True
        
        # Admin SFD de la bonne SFD et prêt accordé
        if hasattr(request.user, 'administrateurssfd'):
            try:
                user_sfd = request.user.administrateurssfd.sfd
                
                # Vérifier SFD
                if hasattr(obj.client, 'compte_epargne'):
                    client_sfd = obj.client.compte_epargne.agent_validateur.sfd
                    if client_sfd != user_sfd:
                        return False
                
                # Vérifier que le prêt peut être décaissé
                return obj.statut == 'accorde'
            except (ObjectDoesNotExist, AttributeError):
                return False
        
        return False


class CanMakeRepayment(BasePermission):
    """
    Permission pour effectuer des remboursements
    Seuls les clients propriétaires du prêt peuvent rembourser
    """
    
    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                hasattr(request.user, 'client'))
    
    def has_object_permission(self, request, view, obj):
        # Vérifier que c'est le client propriétaire du prêt
        if hasattr(obj, 'loan'):
            return obj.loan.client.user == request.user
        elif hasattr(obj, 'client'):
            return obj.client.user == request.user
        return False


class CanViewCreditScore(BasePermission):
    """
    Permission pour consulter le score de crédit
    Superviseurs et admins de la SFD, plus le client lui-même
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Client peut voir son propre score
        if hasattr(request.user, 'client'):
            return obj == request.user.client
        
        # Admin plateforme peut tout voir
        if hasattr(request.user, 'adminplateforme'):
            return True
        
        # Superviseur et Admin SFD de la bonne SFD
        if hasattr(request.user, 'superviseurssfd') or hasattr(request.user, 'administrateurssfd'):
            try:
                if hasattr(request.user, 'superviseurssfd'):
                    user_sfd = request.user.superviseurssfd.sfd
                else:
                    user_sfd = request.user.administrateurssfd.sfd
                
                # Vérifier SFD via compte épargne
                if hasattr(obj, 'compte_epargne'):
                    return obj.compte_epargne.agent_validateur.sfd == user_sfd
            except (ObjectDoesNotExist, AttributeError):
                pass
        
        return False


# =============================================================================
# PERMISSIONS COMBINÉES
# =============================================================================

class LoanApplicationPermission(BasePermission):
    """
    Permission globale pour les demandes de prêt selon le rôle
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Permissions selon l'action
        action = getattr(view, 'action', None)
        
        # Création de demande : clients seulement
        if action == 'create':
            return hasattr(request.user, 'client')
        
        # Actions de lecture : tous les rôles autorisés
        if action in ['list', 'retrieve']:
            return any([
                hasattr(request.user, 'client'),
                hasattr(request.user, 'superviseurssfd'),
                hasattr(request.user, 'administrateurssfd'),
                hasattr(request.user, 'adminplateforme')
            ])
        
        # Actions de modification : selon le workflow
        if action in ['update', 'partial_update']:
            return any([
                hasattr(request.user, 'superviseurssfd'),
                hasattr(request.user, 'administrateurssfd'),
                hasattr(request.user, 'adminplateforme')
            ])
        
        # Suppression : admins seulement
        if action == 'destroy':
            return any([
                hasattr(request.user, 'administrateurssfd'),
                hasattr(request.user, 'adminplateforme')
            ])
        
        return True
    
    def has_object_permission(self, request, view, obj):
        action = getattr(view, 'action', None)
        
        # Admin plateforme a tous les droits
        if hasattr(request.user, 'adminplateforme'):
            return True
        
        # Client : accès lecture seule à ses propres demandes
        if hasattr(request.user, 'client'):
            if action in ['retrieve']:
                return obj.client.user == request.user
            return False
        
        # Superviseur : examiner les demandes de sa SFD
        if hasattr(request.user, 'superviseurssfd'):
            try:
                user_sfd = request.user.superviseurssfd.sfd
                if hasattr(obj.client, 'compte_epargne'):
                    client_sfd = obj.client.compte_epargne.agent_validateur.sfd
                    return client_sfd == user_sfd
            except (ObjectDoesNotExist, AttributeError):
                pass
        
        # Admin SFD : valider les demandes transférées de sa SFD
        if hasattr(request.user, 'administrateurssfd'):
            try:
                user_sfd = request.user.administrateurssfd.sfd
                if hasattr(obj.client, 'compte_epargne'):
                    client_sfd = obj.client.compte_epargne.agent_validateur.sfd
                    return client_sfd == user_sfd
            except (ObjectDoesNotExist, AttributeError):
                pass
        
        return False


class LoanPermission(BasePermission):
    """
    Permission globale pour les prêts accordés
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Seuls certains rôles peuvent accéder aux prêts
        return any([
            hasattr(request.user, 'client'),
            hasattr(request.user, 'superviseurssfd'),
            hasattr(request.user, 'administrateurssfd'),
            hasattr(request.user, 'adminplateforme')
        ])
    
    def has_object_permission(self, request, view, obj):
        # Admin plateforme a tous les droits
        if hasattr(request.user, 'adminplateforme'):
            return True
        
        # Client : ses propres prêts seulement
        if hasattr(request.user, 'client'):
            return obj.client.user == request.user
        
        # Superviseur et Admin SFD : prêts de leur SFD
        if hasattr(request.user, 'superviseurssfd') or hasattr(request.user, 'administrateurssfd'):
            try:
                if hasattr(request.user, 'superviseurssfd'):
                    user_sfd = request.user.superviseurssfd.sfd
                else:
                    user_sfd = request.user.administrateurssfd.sfd
                
                if hasattr(obj.client, 'compte_epargne'):
                    client_sfd = obj.client.compte_epargne.agent_validateur.sfd
                    return client_sfd == user_sfd
            except (ObjectDoesNotExist, AttributeError):
                pass
        
        return False
