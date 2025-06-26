from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    # Authentification
    InscriptionAPIView,
    LoginView,
    TokenRefreshViewCustom,
    # ViewSets API REST
    ClientViewSet,
    AgentSFDReadOnlyViewSet,
    SuperviseurSFDViewSet,
    AdministrateurSFDViewSet,
    AdminPlateformeViewSet,
    SFDAPIViewSet,
    # ViewSets Admin
    AgentSFDViewSet,
    SuperviseurSFDViewSet,
    AdministrateurSFDViewSet,
    AdminPlateformeViewSet,
    SFDViewSet,
)
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

# Router pour l'API REST (lecture)
api_router = DefaultRouter()
api_router.register(r'clients', ClientViewSet, basename='client')
api_router.register(r'agents-sfd', AgentSFDReadOnlyViewSet, basename='agent-sfd-api')
api_router.register(r'superviseurs-sfd', SuperviseurSFDViewSet, basename='superviseur-sfd-api')
api_router.register(r'administrateurs-sfd', AdministrateurSFDViewSet, basename='administrateur-sfd-api')
api_router.register(r'admin-plateforme', AdminPlateformeViewSet, basename='admin-plateforme-api')
api_router.register(r'sfds', SFDAPIViewSet, basename='sfd-api')

# Router pour l'administration (CRUD)
admin_router = DefaultRouter()
admin_router.register(r'agents-sfd', AgentSFDViewSet, basename='agent-sfd-admin')
admin_router.register(r'superviseurs-sfd', SuperviseurSFDViewSet, basename='superviseur-sfd-admin')
admin_router.register(r'administrateurs-sfd', AdministrateurSFDViewSet, basename='administrateur-sfd-admin')
admin_router.register(r'admins-plateforme', AdminPlateformeViewSet, basename='admin-plateforme-admin')
admin_router.register(r'sfd', SFDViewSet, basename='sfd-admin')

urlpatterns = [
    # Authentification
    path('auth/inscription/', InscriptionAPIView.as_view(), name='inscription'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/token/refresh/', TokenRefreshViewCustom.as_view(), name='token_refresh'),
    
    # API REST (séparée de l'admin)
    path('api/accounts/', include(api_router.urls)),
    
    # Administration (endpoints pour gestion des comptes)
    path('api/', include(admin_router.urls)),
    
    # Documentation
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
