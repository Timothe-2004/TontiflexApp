from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import (
    # Accounts ViewSets
    ClientViewSet, AdministrateurSFDViewSet, AgentSFDViewSet, 
    SFDViewSet,
    # Tontines ViewSets
    AdhesionViewSet, TontineViewSet, TontineParticipantViewSet, 
    CotisationViewSet, RetraitViewSet, SoldeTontineViewSet, CarnetCotisationViewSet,
    # Mobile Money ViewSets
    TransactionMobileMoneyViewSet, OperateurMobileMoneyViewSet,
    # Notifications ViewSets
    NotificationViewSet
)

router = DefaultRouter()

# Routes pour les comptes (accounts)
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'administrateurs-sfd', AdministrateurSFDViewSet, basename='administrateursfd')
router.register(r'agents-sfd', AgentSFDViewSet, basename='agentsfd')
router.register(r'sfds', SFDViewSet, basename='sfd')

# Routes pour les tontines
router.register(r'adhesions', AdhesionViewSet, basename='adhesion')
router.register(r'tontines', TontineViewSet, basename='tontine')
router.register(r'participants', TontineParticipantViewSet, basename='participant')
router.register(r'cotisations', CotisationViewSet, basename='cotisation')
router.register(r'retraits', RetraitViewSet, basename='retrait')
router.register(r'soldes-tontine', SoldeTontineViewSet, basename='soldetontine')
router.register(r'carnets-cotisation', CarnetCotisationViewSet, basename='carnetcotisation')

# Routes pour Mobile Money
router.register(r'transactions-mobile-money', TransactionMobileMoneyViewSet, basename='transactionmobilemoney')
router.register(r'operateurs-mobile-money', OperateurMobileMoneyViewSet, basename='operateurmobilemoney')

# Routes pour les notifications
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path('api/', include(router.urls)),
]
