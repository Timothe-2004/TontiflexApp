"""
URLs pour le module Payments KKiaPay
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import PaymentViewSet, PaymentWidgetView, TransactionFromTokenView, GeneratePaymentLinkView
from .webhooks import webhook_view_function

router = DefaultRouter()
router.register(r'transactions', PaymentViewSet, basename='payment')

urlpatterns = [
    # Base route pour les paiements
    path('payments/', include(router.urls)),
    
    # Webhook KKiaPay - utilise la vue fonction avec CSRF exempt
    path('payments/webhook/', webhook_view_function, name='kkiapay-webhook'),

    # Widget HTML (GET) et API token (GET)
    path('payments/widget/', PaymentWidgetView.as_view(), name='kkiapay-widget'),
    path('api/payments/transaction-from-token/', TransactionFromTokenView.as_view(), name='kkiapay-transaction-from-token'),
    path('api/payments/generate-link/', GeneratePaymentLinkView.as_view(), name='kkiapay-generate-link'),
]
