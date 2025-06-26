from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import TransactionMobileMoneyViewSet, OperateurMobileMoneyViewSet

router = DefaultRouter()
router.register(r'transactions', TransactionMobileMoneyViewSet, basename='transaction')
router.register(r'operateurs', OperateurMobileMoneyViewSet, basename='operateur')

urlpatterns = [
    path('api/mobile-money/', include(router.urls)),
]
