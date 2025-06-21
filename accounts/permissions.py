from rest_framework import permissions
from accounts.models import AdminPlateforme
from django.contrib.auth.models import User

class IsAdminPlateformeOrSuperuser(permissions.BasePermission):
    """
    Permission pour restreindre la création de comptes SFD/Admin aux ADMIN_PLATEFORME ou superusers Django.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        # Superuser Django
        if user.is_superuser:
            return True
        # AdminPlateforme (lié à User)
        try:
            return AdminPlateforme.objects.filter(user=user, est_actif=True).exists()
        except Exception:
            return False
