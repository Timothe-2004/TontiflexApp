from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import (
    # Savings ViewSets
    SavingsAccountViewSet, SavingsTransactionViewSet
)

router = DefaultRouter()

# Routes pour les comptes épargne
router.register(r'accounts', SavingsAccountViewSet, basename='savings-account')
router.register(r'transactions', SavingsTransactionViewSet, basename='savings-transaction')

urlpatterns = [
    path('', include(router.urls)),
]
