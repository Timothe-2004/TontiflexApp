from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    InscriptionAPIView,
    AgentSFDViewSet,
    SuperviseurSFDViewSet,
    AdministrateurSFDViewSet,
    AdminPlateformeViewSet,
    LoginView,
    TokenRefreshViewCustom,
    SFDViewSet,  # Ajout du ViewSet SFD
)
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

router = DefaultRouter()
router.register(r'admin/agents-sfd', AgentSFDViewSet, basename='agent-sfd')
router.register(r'admin/superviseurs-sfd', SuperviseurSFDViewSet, basename='superviseur-sfd')
router.register(r'admin/administrateurs-sfd', AdministrateurSFDViewSet, basename='administrateur-sfd')
router.register(r'admin/admins-plateforme', AdminPlateformeViewSet, basename='admin-plateforme')
router.register(r'admin/management/sfd', SFDViewSet, basename='sfd')  # Ajout du routeur SFD

urlpatterns = [
    path('auth/inscription/', InscriptionAPIView.as_view(), name='inscription'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/token/refresh/', TokenRefreshViewCustom.as_view(), name='token_refresh'),
    path('', include(router.urls)),
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
