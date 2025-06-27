"""
URLs pour le module Payments KKiaPay
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import PaymentViewSet, webhook_view, PaymentWidgetView, TransactionFromTokenView, GeneratePaymentLinkView

router = DefaultRouter()
router.register(r'transactions', PaymentViewSet, basename='payment')

urlpatterns = [
    # Base route pour les paiements
    path('payments/', include(router.urls)),
    
    # Webhook KKiaPay
    path('payments/webhook/', webhook_view, name='kkiapay-webhook'),

    # Widget HTML (GET) et API token (GET)
    path('payments/widget/', PaymentWidgetView.as_view(), name='kkiapay-widget'),
    path('api/payments/transaction-from-token/', TransactionFromTokenView.as_view(), name='kkiapay-transaction-from-token'),
    path('api/payments/generate-link/', GeneratePaymentLinkView.as_view(), name='kkiapay-generate-link'),
]
