"""
Permissions pour le module Savings.
Gère les permissions basées sur les rôles pour les comptes épargne et transactions.
"""
from rest_framework import permissions
from accounts.models import User


class IsSavingsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permission personnalisée pour permettre aux propriétaires de compte épargne
    de voir et modifier leurs données.
    """
    
    def has_object_permission(self, request, view, obj):
        # Pour SavingsAccount : vérifier si l'utilisateur est le client propriétaire
        if hasattr(obj, 'client'):
            return obj.client == request.user
        
        # Pour SavingsTransaction : vérifier via le compte épargne
        if hasattr(obj, 'compte_epargne'):
            return obj.compte_epargne.client == request.user
            
        return False


class IsAgentSFDForSavingsValidation(permissions.BasePermission):
    """
    Permission pour les agents SFD pour valider les demandes de compte épargne.
    """
    
    def has_permission(self, request, view):
        # L'utilisateur doit être un Agent SFD
        return (request.user.is_authenticated and 
                request.user.type_utilisateur == User.TypeUtilisateur.AGENT_SFD)
    
    def has_object_permission(self, request, view, obj):
        # L'agent doit appartenir au même SFD que l'agent validateur du compte
        if hasattr(obj, 'agent_validateur') and obj.agent_validateur:
            return (request.user.type_utilisateur == User.TypeUtilisateur.AGENT_SFD and
                    hasattr(request.user, 'agentsfd') and
                    request.user.agentsfd.sfd == obj.agent_validateur.sfd)
        # Si pas encore validé, n'importe quel agent peut valider
        elif hasattr(obj, 'client'):
            return request.user.type_utilisateur == User.TypeUtilisateur.AGENT_SFD
        return False


class IsSavingsAccountClient(permissions.BasePermission):
    """
    Permission pour vérifier que l'utilisateur est un client avec un compte épargne.
    """
    
    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                request.user.type_utilisateur == User.TypeUtilisateur.CLIENT)


class CanViewSavingsTransactions(permissions.BasePermission):
    """
    Permission pour consulter les transactions d'épargne.
    """
    
    def has_permission(self, request, view):
        # Seuls les clients, agents et superviseurs peuvent voir les transactions
        allowed_types = [
            User.TypeUtilisateur.CLIENT,
            User.TypeUtilisateur.AGENT_SFD,
            User.TypeUtilisateur.SUPERVISEUR_SFD,
            User.TypeUtilisateur.ADMIN_SFD
        ]
        return (request.user.is_authenticated and 
                request.user.type_utilisateur in allowed_types)
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Client : peut voir ses propres transactions
        if user.type_utilisateur == User.TypeUtilisateur.CLIENT:
            return obj.compte_epargne.client == user
        
        # Agent/Superviseur/Admin SFD : peut voir les transactions de leur SFD
        elif user.type_utilisateur in [
            User.TypeUtilisateur.AGENT_SFD,
            User.TypeUtilisateur.SUPERVISEUR_SFD,
            User.TypeUtilisateur.ADMIN_SFD
        ]:
            # Check if transaction account has a validating agent from same SFD
            if (obj.compte_epargne.agent_validateur and 
                hasattr(user, 'agentsfd') and
                user.agentsfd.sfd == obj.compte_epargne.agent_validateur.sfd):
                return True
            elif (obj.compte_epargne.agent_validateur and 
                  hasattr(user, 'superviseurssfd') and
                  user.superviseurssfd.sfd == obj.compte_epargne.agent_validateur.sfd):
                return True
            elif (obj.compte_epargne.agent_validateur and 
                  hasattr(user, 'administrateurssfd') and
                  user.administrateurssfd.sfd == obj.compte_epargne.agent_validateur.sfd):
                return True
            return False
        
        return False


class CanManageSavingsAccounts(permissions.BasePermission):
    """
    Permission pour gérer (créer, valider) les comptes épargne.
    """
    
    def has_permission(self, request, view):
        # Clients peuvent créer des demandes, agents peuvent valider
        allowed_types = [
            User.TypeUtilisateur.CLIENT,
            User.TypeUtilisateur.AGENT_SFD,
            User.TypeUtilisateur.ADMIN_SFD
        ]
        return (request.user.is_authenticated and 
                request.user.type_utilisateur in allowed_types)
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Client : peut gérer sa propre demande
        if user.type_utilisateur == User.TypeUtilisateur.CLIENT:
            return obj.client == user
        
        # Agent/Admin SFD : peut gérer les demandes de leur SFD
        elif user.type_utilisateur in [
            User.TypeUtilisateur.AGENT_SFD,
            User.TypeUtilisateur.ADMIN_SFD
        ]:
            # Agents can manage accounts they validated or any pending account for validation
            if obj.agent_validateur:
                # Check if user is from same SFD as validating agent
                if (hasattr(user, 'agentsfd') and
                    user.agentsfd.sfd == obj.agent_validateur.sfd):
                    return True
                elif (hasattr(user, 'administrateurssfd') and
                      user.administrateurssfd.sfd == obj.agent_validateur.sfd):
                    return True
            else:
                # Account not yet validated, any agent can validate
                return True
            return False
        
        return False


class CanProcessWithdrawals(permissions.BasePermission):
    """
    Permission pour traiter les demandes de retrait.
    """
    
    def has_permission(self, request, view):
        # Seuls les agents et admin SFD peuvent approuver les retraits
        allowed_types = [
            User.TypeUtilisateur.AGENT_SFD,
            User.TypeUtilisateur.ADMIN_SFD
        ]
        return (request.user.is_authenticated and 
                request.user.type_utilisateur in allowed_types)
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Agent/Admin SFD : peut traiter les retraits de leur SFD
        if user.type_utilisateur in [
            User.TypeUtilisateur.AGENT_SFD,
            User.TypeUtilisateur.ADMIN_SFD
        ]:
            # Check if user is from same SFD as account's validating agent
            if (obj.compte_epargne.agent_validateur and
                hasattr(user, 'agentsfd') and
                user.agentsfd.sfd == obj.compte_epargne.agent_validateur.sfd):
                return True
            elif (obj.compte_epargne.agent_validateur and
                  hasattr(user, 'administrateurssfd') and
                  user.administrateurssfd.sfd == obj.compte_epargne.agent_validateur.sfd):
                return True
            return False
        
        return False


class IsAdminSFDForSavings(permissions.BasePermission):
    """
    Permission pour les actions réservées aux Admin SFD sur les comptes épargne.
    """
    
    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                request.user.type_utilisateur == User.TypeUtilisateur.ADMIN_SFD)
    
    def has_object_permission(self, request, view, obj):
        # Admin SFD : peut agir sur les comptes de son SFD
        if hasattr(obj, 'client') and hasattr(obj, 'agent_validateur'):
            # Check if user is admin of same SFD as validating agent
            return (obj.agent_validateur and
                    hasattr(request.user, 'administrateurssfd') and
                    request.user.administrateurssfd.sfd == obj.agent_validateur.sfd)
        elif hasattr(obj, 'compte_epargne'):
            # Check if user is admin of same SFD as account's validating agent
            return (obj.compte_epargne.agent_validateur and
                    hasattr(request.user, 'administrateurssfd') and
                    request.user.administrateurssfd.sfd == obj.compte_epargne.agent_validateur.sfd)
        return False


# ============================================================================
# PERMISSIONS COMPOSÉES
# ============================================================================

class SavingsAccountPermission(permissions.BasePermission):
    """
    Permission composite pour les comptes épargne selon l'action.
    """
    
    def has_permission(self, request, view):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        action = getattr(view, 'action', None)
        
        # Actions pour les clients
        if action in ['create_request', 'my_account', 'deposit', 'pay_fees']:
            return user.type_utilisateur == User.TypeUtilisateur.CLIENT
        
        # Actions pour les agents SFD
        elif action in ['validate_request', 'list_pending']:
            return user.type_utilisateur == User.TypeUtilisateur.AGENT_SFD
        
        # Actions pour les admin SFD
        elif action in ['list', 'retrieve', 'statistics']:
            return user.type_utilisateur in [
                User.TypeUtilisateur.AGENT_SFD,
                User.TypeUtilisateur.ADMIN_SFD
            ]
        
        # Lecture générale
        elif action in ['retrieve']:
            return user.type_utilisateur in [
                User.TypeUtilisateur.CLIENT,
                User.TypeUtilisateur.AGENT_SFD,
                User.TypeUtilisateur.ADMIN_SFD
            ]
        
        return False
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        action = getattr(view, 'action', None)
        
        # Client : peut agir sur son propre compte
        if user.type_utilisateur == User.TypeUtilisateur.CLIENT:
            return obj.client == user
        
        # Agent/Admin SFD : peut agir sur les comptes de leur SFD
        elif user.type_utilisateur in [
            User.TypeUtilisateur.AGENT_SFD,
            User.TypeUtilisateur.ADMIN_SFD
        ]:
            # Check if user is from same SFD as account's validating agent
            if (obj.agent_validateur and
                hasattr(user, 'agentsfd') and
                user.agentsfd.sfd == obj.agent_validateur.sfd):
                return True
            elif (obj.agent_validateur and
                  hasattr(user, 'administrateurssfd') and
                  user.administrateurssfd.sfd == obj.agent_validateur.sfd):
                return True
            return False
        
        return False


class SavingsTransactionPermission(permissions.BasePermission):
    """
    Permission composite pour les transactions d'épargne selon l'action.
    """
    
    def has_permission(self, request, view):
        user = request.user
        
        if not user.is_authenticated:
            return False
        
        action = getattr(view, 'action', None)
        
        # Actions pour les clients
        if action in ['deposit', 'withdraw']:
            return user.type_utilisateur == User.TypeUtilisateur.CLIENT
        
        # Actions pour consultation
        elif action in ['list', 'retrieve', 'history']:
            return user.type_utilisateur in [
                User.TypeUtilisateur.CLIENT,
                User.TypeUtilisateur.AGENT_SFD,
                User.TypeUtilisateur.ADMIN_SFD
            ]
        
        # Actions pour agents (approuver retraits)
        elif action in ['approve_withdrawal']:
            return user.type_utilisateur in [
                User.TypeUtilisateur.AGENT_SFD,
                User.TypeUtilisateur.ADMIN_SFD
            ]
        
        return False
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Client : peut agir sur ses propres transactions
        if user.type_utilisateur == User.TypeUtilisateur.CLIENT:
            return obj.compte_epargne.client == user
        
        # Agent/Admin SFD : peut agir sur les transactions de leur SFD
        elif user.type_utilisateur in [
            User.TypeUtilisateur.AGENT_SFD,
            User.TypeUtilisateur.ADMIN_SFD
        ]:
            # Check if user is from same SFD as account's validating agent
            if (obj.compte_epargne.agent_validateur and
                hasattr(user, 'agentsfd') and
                user.agentsfd.sfd == obj.compte_epargne.agent_validateur.sfd):
                return True
            elif (obj.compte_epargne.agent_validateur and
                  hasattr(user, 'administrateurssfd') and
                  user.administrateurssfd.sfd == obj.compte_epargne.agent_validateur.sfd):
                return True
            return False
        
        return False
