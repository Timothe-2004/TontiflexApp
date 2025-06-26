"""
URLs pour le module Payments KKiaPay
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import PaymentViewSet, webhook_view

router = DefaultRouter()
router.register(r'transactions', PaymentViewSet, basename='payment')

urlpatterns = [
    # Base route pour les paiements
    path('payments/', include(router.urls)),
    
    # Webhook KKiaPay
    path('payments/webhook/', webhook_view, name='kkiapay-webhook'),
]
