"""
URL configuration for tontiflex project.

Structure réorganisée avec namespaces séparés pour chaque module.
"""

from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Documentation API centralisée à la racine
    path('', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui-home'),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    
    # API REST avec namespaces organisés sous /api/
    path('api/', include('accounts.urls')),      # /api/accounts/ et /api/auth/
    path('api/', include('tontines.urls')),      # /api/tontines/
    path('api/', include('savings.urls')),       # /api/savings/
    path('api/', include('loans.urls')),         # /api/loans/
    # path('api/', include('mobile_money.urls')),  # MODULE SUPPRIMÉ - MIGRATION VERS KKIAPAY
    path('api/', include('payments.urls')),      # /api/payments/ - MODULE KKIAPAY UNIQUE
    path('api/', include('notifications.urls')), # /api/notifications/
    path('api/', include('accounts.urls_webhook')),
]
