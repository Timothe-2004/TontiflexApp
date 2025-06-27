from django.urls import path
from .views_webhook import kkiapay_webhook

urlpatterns = [
    path("api/payments/webhook/", kkiapay_webhook, name="kkiapay_webhook"),
]
