"""
URL configuration for tontiflex project.

Structure réorganisée avec namespaces séparés pour chaque module.
"""

from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API REST avec namespaces organisés
    path('', include('accounts.urls')),      # /api/accounts/ et /auth/
    path('', include('tontines.urls')),      # /api/tontines/
    path('', include('savings.urls')),       # /api/savings/
    path('', include('mobile_money.urls')),  # /api/mobile-money/
    path('', include('notifications.urls')), # /api/notifications/
    
    # Documentation API centralisée
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui-home'),
]
