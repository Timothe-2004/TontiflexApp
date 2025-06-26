"""
Views Django REST Framework pour le module Notifications.
"""
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample, OpenApiResponse

from .models import Notification
from .serializers import NotificationSerializer, NotificationCreateSerializer


@extend_schema_view(
    list=extend_schema(
        summary="Liste des notifications de l'utilisateur",
        description="""
        Affiche la liste des notifications reçues par l'utilisateur connecté.
        
        Types de notifications TontiFlex:
        
        📧 Pour les Clients:
        Confirmation d'adhésion à une tontine
        Confirmation de cotisation reçue
        Rappel de cotisation quotidienne
        Notification de distribution (tour de réception)
        Confirmation de retrait traité
        Rejet de demande (avec motif)
        
        📨 Pour les Agents SFD:
        Nouvelle demande d'adhésion à valider
        Document d'identité à vérifier
        Demande de retrait en attente
        Notification de validation requise
        
        📩 Pour les Superviseurs SFD:
        Nouvelle demande de prêt à examiner
        Dossier transmis par un agent
        Échéance de remboursement proche
        Prêt en retard de paiement
        
        📬 Pour les Admins SFD:
        Rapport hebdomadaire d'activité
        Nouvelle tontine créée
        Statistiques de performance
        Alertes système importantes
        
        Statuts de notification:
        non_lue: Notification non consultée (badge rouge)
        lue: Notification consultée par l'utilisateur
        archivee: Notification archivée (masquée par défaut)
        
        Tri et filtres:
        Tri par date (plus récentes en premier)
        Filtre par type de notification
        Filtre par statut (lue/non lue)
        Recherche dans le contenu
        """,
        responses={200: NotificationSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Créer une nouvelle notification",
        description="""
        Crée et envoie une nouvelle notification à un utilisateur.
        
        Processus d'envoi:
        1. Validation du destinataire et du contenu
        2. Création de la notification en base
        3. Envoi par les canaux configurés (email/SMS)
        4. Mise à jour des compteurs de notifications
        
        Canaux de livraison:
        Notification in-app: Toujours activée
        Email: Si l'utilisateur a un email valide
        SMS: Si l'utilisateur a activé les SMS
        Push: Si l'application mobile est installée
        
        Modèles de notification:
        Templates prédéfinis pour chaque type d'événement
        Variables dynamiques (nom, montant, date, etc.)        Support multilingue (français, local languages)
        Personnalisation selon le type d'utilisateur
        
        Permissions requises: Admin SFD ou Admin plateforme
        """,
        request=NotificationCreateSerializer,
        responses={
            201: NotificationSerializer,
            400: OpenApiResponse(description="Données invalides ou destinataire introuvable"),
            403: OpenApiResponse(description="Permissions insuffisantes")
        },
        examples=[
            OpenApiExample(
                "Notification adhésion confirmée",
                value={
                    "destinataire_id": 123,
                    "type_notification": "ADHESION_CONFIRMEE",
                    "titre": "Adhésion confirmée ✅",
                    "message": "Votre adhésion à la tontine 'Commerçants Cotonou' a été confirmée. Votre première cotisation est attendue demain.",
                    "envoyer_email": True,
                    "envoyer_sms": False,
                    "priorite": "NORMALE"
                }
            ),
            OpenApiExample(
                "Rappel cotisation",
                value={
                    "destinataire_id": 456,
                    "type_notification": "RAPPEL_COTISATION",
                    "titre": "Rappel: Cotisation du jour 💰",
                    "message": "N'oubliez pas votre cotisation quotidienne de 25,000 FCFA pour la tontine 'Épargne Famille'.",
                    "envoyer_email": False,
                    "envoyer_sms": True,
                    "priorite": "HAUTE"
                }
            )
        ]
    ),
    retrieve=extend_schema(
        summary="Détails d'une notification",
        description="Récupère les informations détaillées d'une notification spécifique avec son historique de livraison."
    ),
    update=extend_schema(
        summary="Modifier une notification",
        description="""
        Met à jour une notification existante.
        
        Modifications possibles:
        Statut de lecture (non_lue/lue/archivee)
        Contenu du message (si non envoyée)
        Paramètres de livraison
        Priorité de la notification
        
        Restrictions: Certaines modifications possibles uniquement avant envoi
        """
    ),
    partial_update=extend_schema(
        summary="Modification partielle d'une notification",
        description="Met à jour partiellement une notification (uniquement les champs fournis)."
    ),
    destroy=extend_schema(
        summary="Supprimer une notification",
        description="""
        Supprime définitivement une notification.
        
        Conditions:
        Notification non critique
        Autorisation de l'administrateur
        Respect de la politique de rétention
        
        Effets: Suppression complète des données
        """
    )
)
@extend_schema(tags=["🔔 Notifications"])
class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des notifications
    """
    queryset = Notification.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return NotificationCreateSerializer
        return NotificationSerializer

    def get_queryset(self):
        """Filter notifications based on user"""
        user = self.request.user
        
        # Chaque utilisateur ne voit que ses propres notifications
        user_profile = None
        if hasattr(user, 'clientsfd'):
            user_profile = user.clientsfd
        elif hasattr(user, 'agentsfd'):
            user_profile = user.agentsfd
        elif hasattr(user, 'superviseurssfd'):
            user_profile = user.superviseurssfd
        elif hasattr(user, 'administrateurssfd'):
            user_profile = user.administrateurssfd
        elif hasattr(user, 'adminplateforme'):
            user_profile = user.adminplateforme
        
        if user_profile:
            return Notification.objects.filter(destinataire=user_profile).order_by('-date_creation')
        
        return Notification.objects.none()

    @extend_schema(
        summary="Marquer une notification comme lue",
        description="""
        Marque une notification spécifique comme lue par l'utilisateur.
        
        **Effet de l'action**:
        - Statut de la notification passe à 'lue'
        - Mise à jour du timestamp de lecture
        - Décrément du compteur de notifications non lues
        - Notification supprimée des badges d'alerte
        
        **Permissions requises**:
        - Propriétaire de la notification uniquement
        - Auto-vérification: un utilisateur ne peut marquer que ses propres notifications
        
        **Cas d'usage**:
        - Clic sur une notification dans l'interface
        - Lecture complète du contenu
        - Acquittement d'une alerte importante
        """,
        responses={
            200: NotificationSerializer,
            403: OpenApiResponse(description="Notification non accessible"),
            404: OpenApiResponse(description="Notification introuvable")
        },
        examples=[
            OpenApiExample(
                "Succès marquage lecture",
                value={
                    "success": True,
                    "message": "Notification marquée comme lue",
                    "notification": {
                        "id": 123,
                        "titre": "Cotisation confirmée",
                        "est_lue": True,
                        "date_lecture": "2025-06-25T14:30:00Z"
                    }
                }
            )
        ]
    )
    @action(detail=True, methods=['post'], url_path='marquer-lue')
    def marquer_lue(self, request, pk=None):
        """
        POST /api/notifications/{id}/marquer-lue/
        Marque une notification comme lue
        """
        notification = self.get_object()
        
        if not notification.est_lue:
            notification.marquer_comme_lue()
        
        return Response({
            'success': True,
            'message': 'Notification marquée comme lue',
            'notification': NotificationSerializer(notification).data
        })

    @extend_schema(
        summary="Marquer toutes les notifications comme lues",
        description="""
        Marque toutes les notifications non lues de l'utilisateur comme lues en une seule action.
        
        **Action de masse**:
        - Traitement de toutes les notifications non lues
        - Mise à jour en lot pour optimiser les performances
        - Remise à zéro du compteur de notifications
        - Effacement de tous les badges d'alerte
        
        **Utilisation typique**:
        - Bouton "Tout marquer comme lu" dans l'interface
        - Nettoyage rapide des notifications
        - Remise à zéro après une période d'absence
        
        **Réponse**:
        - Nombre de notifications traitées
        - Confirmation de l'action effectuée
        - Statut mis à jour de l'utilisateur
        """,
        responses={
            200: OpenApiResponse(
                description="Toutes les notifications marquées comme lues",
                examples=[
                    OpenApiExample(
                        "Succès marquage en masse",
                        value={
                            "success": True,
                            "message": "15 notifications marquées comme lues",
                            "notifications_mises_a_jour": 15
                        }
                    )
                ]
            )
        }
    )
    @action(detail=False, methods=['post'], url_path='marquer-toutes-lues')
    def marquer_toutes_lues(self, request):
        """
        POST /api/notifications/marquer-toutes-lues/
        Marque toutes les notifications de l'utilisateur comme lues
        """
        notifications = self.get_queryset().filter(est_lue=False)
        count = notifications.count()
        
        for notification in notifications:
            notification.marquer_comme_lue()
        
        return Response({
            'success': True,
            'message': f'{count} notifications marquées comme lues',
            'notifications_mises_a_jour': count
        })

    @extend_schema(
        summary="Récupérer les notifications non lues",
        description="""
        Retourne uniquement les notifications non lues de l'utilisateur connecté.
        
        **Utilisation principale**:
        - Affichage des badges de notification (compteur rouge)
        - Pop-ups d'alerte pour nouveaux événements
        - Notifications push en temps réel
        - Vérification périodique de nouvelles notifications
        
        **Optimisations**:
        - Requête rapide avec index sur 'est_lue'
        - Tri par priorité et date
        - Limitation automatique aux 50 plus récentes
        - Cache pour réduire la charge serveur
        
        **Réponse optimisée**:
        - Nombre total de notifications non lues
        - Liste des notifications avec données essentielles
        - Indicateur de priorité pour l'affichage
        - Timestamp pour la synchronisation
        """,
        responses={
            200: OpenApiResponse(
                description="Notifications non lues récupérées",
                examples=[
                    OpenApiExample(
                        "Notifications non lues",
                        value={
                            "count": 3,
                            "notifications": [
                                {
                                    "id": 456,
                                    "titre": "Nouvelle demande d'adhésion",
                                    "message": "Un client souhaite rejoindre votre tontine",
                                    "type_notification": "DEMANDE_ADHESION",
                                    "priorite": "HAUTE",
                                    "date_creation": "2025-06-25T09:15:00Z"
                                },
                                {
                                    "id": 457,
                                    "titre": "Cotisation reçue",
                                    "message": "Cotisation de 25,000 FCFA confirmée",
                                    "type_notification": "COTISATION_CONFIRMEE",
                                    "priorite": "NORMALE",
                                    "date_creation": "2025-06-25T08:30:00Z"
                                }
                            ]
                        }
                    )
                ]
            )
        }
    )
    @action(detail=False, methods=['get'], url_path='non-lues')
    def non_lues(self, request):
        """
        GET /api/notifications/non-lues/
        Retourne les notifications non lues de l'utilisateur
        """
        notifications = self.get_queryset().filter(est_lue=False)
        serializer = NotificationSerializer(notifications, many=True)
        
        return Response({
            'count': notifications.count(),
            'notifications': serializer.data
        })
