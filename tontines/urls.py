from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import (
    # Tontines ViewSets seulement
    AdhesionViewSet, TontineViewSet, TontineParticipantViewSet, 
    CotisationViewSet, RetraitViewSet, SoldeTontineViewSet, CarnetCotisationViewSet
)

router = DefaultRouter()

# Routes pour les tontines uniquement
router.register(r'adhesions', AdhesionViewSet, basename='adhesion')
router.register(r'tontines', TontineViewSet, basename='tontine')
router.register(r'participants', TontineParticipantViewSet, basename='participant')
router.register(r'cotisations', CotisationViewSet, basename='cotisation')
router.register(r'retraits', RetraitViewSet, basename='retrait')
router.register(r'soldes-tontine', SoldeTontineViewSet, basename='soldetontine')
router.register(r'carnets-cotisation', CarnetCotisationViewSet, basename='carnetcotisation')

urlpatterns = [
    path('api/tontines/', include(router.urls)),
]
