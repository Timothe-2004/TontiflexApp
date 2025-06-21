from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from decimal import Decimal
import django.db.transaction
from django.utils import timezone
from django.db.models import Sum, Count

# Import des modèles
from accounts.models import Client, AdministrateurSFD, AgentSFD, SFD
from .models import Adhesion, Tontine, TontineParticipant, Cotisation, Retrait, SoldeTontine, CarnetCotisation
from mobile_money.models import TransactionMobileMoney, OperateurMobileMoney
from notifications.models import Notification

# Import des serializers
from .serializers import (
    ClientSerializer, AdministrateurSFDSerializer, AgentSFDSerializer, 
    SFDSerializer,
    AdhesionSerializer, TontineSerializer, TontineParticipantSerializer, 
    CotisationSerializer, RetraitSerializer, SoldeTontineSerializer, CarnetCotisationSerializer,
    TransactionMobileMoneySerializer, OperateurMobileMoneySerializer,
    NotificationSerializer,
    # Custom action serializers
    ValiderAgentRequestSerializer, PayerRequestSerializer, IntegrerRequestSerializer,
    CotiserRequestSerializer
)

# =============================================================================
# VIEWSETS POUR ACCOUNTS
# =============================================================================

class ClientViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des clients
    """
    queryset = Client.objects.all()
    serializer_class = ClientSerializer

class AdministrateurSFDViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des administrateurs SFD
    """
    queryset = AdministrateurSFD.objects.all()
    serializer_class = AdministrateurSFDSerializer

class AgentSFDViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des agents SFD
    """
    queryset = AgentSFD.objects.all()
    serializer_class = AgentSFDSerializer

class SFDViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des SFD
    """
    queryset = SFD.objects.all()
    serializer_class = SFDSerializer


# =============================================================================
# VIEWSETS POUR TONTINES
# =============================================================================

class AdhesionViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des demandes d'adhésion à une tontine
    """
    queryset = Adhesion.objects.all()
    serializer_class = AdhesionSerializer   
    @action(detail=True, methods=['post'], url_path='valider-agent')
    def valider_agent(self, request, pk=None):
        """
        Action pour valider une demande d'adhésion par un agent SFD
        """
        adhesion = self.get_object()
        serializer = ValiderAgentRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                with django.db.transaction.atomic():
                    # Logique de validation par agent
                    adhesion.statut = 'validee_agent'
                    adhesion.agent_validateur = serializer.validated_data.get('agent')
                    adhesion.commentaires_agent = serializer.validated_data.get('commentaires', '')
                    adhesion.date_validation_agent = timezone.now()
                    adhesion.save()
                    
                return Response({
                    'success': True,
                    'message': 'Demande validée par agent',
                    'adhesion': AdhesionSerializer(adhesion).data
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)    @action(detail=True, methods=['post'], url_path='payer')
    def payer(self, request, pk=None):
        """
        Action pour effectuer le paiement des frais d'adhésion
        """
        adhesion = self.get_object()
        serializer = PayerRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                with django.db.transaction.atomic():
                    # Logique de paiement via Mobile Money
                    numero_telephone = serializer.validated_data['numero_mobile_money']
                    operateur = serializer.validated_data['operateur']
                    
                    # Créer une transaction Mobile Money
                    transaction = TransactionMobileMoney.objects.create(
                        numero_telephone=numero_telephone,
                        montant=adhesion.tontine.frais_adhesion,
                        type_transaction='paiement',
                        statut='en_cours',
                        reference_externe=f"ADH_{adhesion.id}_{int(timezone.now().timestamp())}",
                        description=f"Paiement adhésion tontine {adhesion.tontine.nom}"
                    )
                    
                    adhesion.statut = 'paiement_effectue'
                    adhesion.transaction_paiement = transaction
                    adhesion.save()
                    
                return Response({
                    'success': True,
                    'message': 'Paiement initié',
                    'transaction_id': transaction.id,
                    'adhesion': AdhesionSerializer(adhesion).data
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)    @action(detail=True, methods=['post'], url_path='integrer')
    def integrer(self, request, pk=None):
        """
        Action pour intégrer un client à la tontine après paiement validé
        """
        adhesion = self.get_object()
        serializer = IntegrerRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                with django.db.transaction.atomic():
                    # Créer le participant à la tontine
                    participant = TontineParticipant.objects.create(
                        tontine=adhesion.tontine,
                        client=adhesion.client,
                        date_adhesion=timezone.now(),
                        montant_cotisation=adhesion.montant_cotisation_propose
                    )
                    
                    # Créer le solde initial pour ce participant
                    SoldeTontine.objects.create(
                        tontine=adhesion.tontine,
                        client=adhesion.client,
                        solde_actuel=Decimal('0.00'),
                        total_cotisations=Decimal('0.00'),
                        total_retraits=Decimal('0.00')
                    )
                    
                    # Créer le carnet de cotisation (31 jours)
                    CarnetCotisation.objects.create(
                        participant=participant,
                        mois=timezone.now().month,
                        annee=timezone.now().year,
                        carnet_data={}  # JSONField vide au début
                    )
                    
                    adhesion.statut = 'integree'
                    adhesion.participant_cree = participant
                    adhesion.save()
                    
                return Response({
                    'success': True,
                    'message': 'Client intégré à la tontine',
                    'participant_id': participant.id,
                    'adhesion': AdhesionSerializer(adhesion).data
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TontineViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des tontines
    """
    queryset = Tontine.objects.all()
    serializer_class = TontineSerializer

class TontineParticipantViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des participants aux tontines
    """
    queryset = TontineParticipant.objects.all()
    serializer_class = TontineParticipantSerializer   
    @action(detail=True, methods=['post'], url_path='cotiser')
    def cotiser(self, request, pk=None):
        """
        Action pour effectuer une cotisation
        """
        participant = self.get_object()
        serializer = CotiserRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                with django.db.transaction.atomic():
                    numero_telephone = serializer.validated_data['numero_telephone']
                    montant = serializer.validated_data['montant']
                    is_commission = serializer.validated_data.get('is_commission', False)
                    
                    # Créer la transaction Mobile Money
                    transaction = TransactionMobileMoney.objects.create(
                        numero_telephone=numero_telephone,
                        montant=montant,
                        type_transaction='cotisation',
                        statut='en_cours',
                        reference_externe=f"COT_{participant.id}_{int(timezone.now().timestamp())}",
                        description=f"Cotisation tontine {participant.tontine.nom}",
                        is_commission=is_commission
                    )
                    
                    # Créer la cotisation
                    cotisation = Cotisation.objects.create(
                        participant=participant,
                        montant=montant,
                        date_cotisation=timezone.now(),
                        transaction_mobile_money=transaction,
                        is_commission_sfd=is_commission
                    )
                    
                    # Mettre à jour le solde
                    solde, created = SoldeTontine.objects.get_or_create(
                        tontine=participant.tontine,
                        client=participant.client,
                        defaults={
                            'solde_actuel': Decimal('0.00'),
                            'total_cotisations': Decimal('0.00'),
                            'total_retraits': Decimal('0.00')
                        }
                    )
                    
                    if not is_commission:
                        solde.solde_actuel += montant
                        solde.total_cotisations += montant
                        solde.save()
                    
                    # Mettre à jour le carnet de cotisation
                    carnet, created = CarnetCotisation.objects.get_or_create(
                        participant=participant,
                        mois=timezone.now().month,
                        annee=timezone.now().year,
                        defaults={'carnet_data': {}}
                    )
                    
                    # Ajouter la cotisation du jour dans le carnet
                    jour = timezone.now().day
                    if not carnet.carnet_data:
                        carnet.carnet_data = {}
                    carnet.carnet_data[str(jour)] = {
                        'montant': str(montant),
                        'transaction_id': transaction.id,
                        'is_commission': is_commission,
                        'timestamp': timezone.now().isoformat()
                    }
                    carnet.save()
                    
                return Response({
                    'success': True,
                    'message': 'Cotisation enregistrée',
                    'cotisation_id': cotisation.id,
                    'transaction_id': transaction.id,
                    'nouveau_solde': solde.solde_actuel if not is_commission else None
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """
        Action pour obtenir les statistiques des participants
        """
        stats = {
            'total_participants': TontineParticipant.objects.count(),
            'participants_actifs': TontineParticipant.objects.filter(date_retrait__isnull=True).count(),
            'total_cotisations': Cotisation.objects.aggregate(total=Sum('montant'))['total'] or 0,
            'cotisations_ce_mois': Cotisation.objects.filter(
                date_cotisation__month=timezone.now().month,
                date_cotisation__year=timezone.now().year
            ).aggregate(total=Sum('montant'))['total'] or 0,
            'commissions_sfd': Cotisation.objects.filter(
                is_commission_sfd=True
            ).aggregate(total=Sum('montant'))['total'] or 0,
        }
        
        return Response(stats, status=status.HTTP_200_OK)

class CotisationViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des cotisations
    """
    queryset = Cotisation.objects.all()
    serializer_class = CotisationSerializer

class RetraitViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des retraits
    """
    queryset = Retrait.objects.all()
    serializer_class = RetraitSerializer

class SoldeTontineViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des soldes par tontine
    """
    queryset = SoldeTontine.objects.all()
    serializer_class = SoldeTontineSerializer

class CarnetCotisationViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des carnets de cotisation (31 jours)
    """
    queryset = CarnetCotisation.objects.all()
    serializer_class = CarnetCotisationSerializer

# =============================================================================
# VIEWSETS POUR MOBILE MONEY
# =============================================================================

class TransactionMobileMoneyViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des transactions Mobile Money
    """
    queryset = TransactionMobileMoney.objects.all()
    serializer_class = TransactionMobileMoneySerializer

class OperateurMobileMoneyViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des opérateurs Mobile Money
    """
    queryset = OperateurMobileMoney.objects.all()
    serializer_class = OperateurMobileMoneySerializer

# =============================================================================
# VIEWSETS POUR NOTIFICATIONS
# =============================================================================

class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des notifications
    """
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
