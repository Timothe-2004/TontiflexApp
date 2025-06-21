from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from .models import Notification
from typing import Dict, List, Optional, Any
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service pour la gestion des notifications du système.
    """
    
    @staticmethod
    def creer_notification(
        utilisateur,
        titre: str,
        message: str,
        canal: str = 'app',
        objet_lie: Optional[Any] = None,
        donnees_supplementaires: Dict = None,
        actions: List[Dict] = None,
        envoyer_immediatement: bool = True
    ) -> Notification:
        """
        Crée une nouvelle notification.
        
        Args:
            utilisateur: L'utilisateur destinataire
            titre: Titre de la notification
            message: Message de la notification
            canal: Canal de diffusion (app, email)
            objet_lie: Objet lié à la notification
            donnees_supplementaires: Données JSON supplémentaires
            actions: Liste des actions disponibles
            envoyer_immediatement: Envoyer immédiatement ou non
            
        Returns:
            Notification: L'instance de notification créée
        """
        try:
            # Préparation des données
            donnees_supplementaires = donnees_supplementaires or {}
            actions = actions or []
            
            # Gestion de l'objet lié
            content_type = None
            object_id = None
            if objet_lie:
                content_type = ContentType.objects.get_for_model(objet_lie)
                object_id = objet_lie.pk
            
            # Création de la notification
            notification = Notification.objects.create(
                utilisateur=utilisateur,
                titre=titre,
                message=message,
                canal=canal,
                content_type=content_type,
                object_id=object_id,
                donnees_supplementaires=donnees_supplementaires,
                actions=actions
            )
            
            # Envoi immédiat si demandé
            if envoyer_immediatement and canal != 'app':
                NotificationService.envoyer_notification(notification)
            
            logger.info(f"Notification créée: {notification.id} pour {utilisateur.username}")
            return notification
            
        except Exception as e:
            logger.error(f"Erreur lors de la création de notification: {str(e)}")
            raise
    
    @staticmethod
    def creer_notification_tontine_adhesion_validee(
        client,
        agent,
        tontine: Any,
        montant_adhesion: float
    ) -> Notification:
        """
        Crée une notification pour une adhésion validée par un agent.
        """
        titre = "Adhésion validée !"
        message = (
            f"Félicitations ! Votre demande d'adhésion a été validée par l'agent "
            f"{agent.get_full_name()}. Vous pouvez maintenant payer les frais "
            f"d'adhésion pour rejoindre la tontine {tontine.nom}."
        )
        
        actions = [
            {
                'type': 'primary',
                'label': f'Payer les frais d\'adhésion ({montant_adhesion} FCFA)',
                'url': f'/tontines/{tontine.id}/payer-adhesion/',
                'method': 'POST',
                'confirm': f'Confirmer le paiement de {montant_adhesion} FCFA ?'
            }
        ]
        
        donnees_supplementaires = {
            'tontine_id': tontine.id,
            'tontine_nom': tontine.nom,
            'agent_id': agent.id,
            'agent_nom': agent.get_full_name(),
            'montant_adhesion': montant_adhesion,
            'type_action': 'paiement_adhesion'
        }
        
        return NotificationService.creer_notification(
            utilisateur=client,
            titre=titre,
            message=message,
            objet_lie=tontine,
            donnees_supplementaires=donnees_supplementaires,
            actions=actions
        )
    
    @staticmethod
    def creer_notification_pret_approuve(
        client,
        pret: Any,
        montant: float,
        taux_interet: float
    ) -> Notification:
        """
        Crée une notification pour un prêt approuvé.
        """
        titre = "Prêt approuvé !"
        message = (
            f"Votre demande de prêt de {montant} FCFA a été approuvée "
            f"avec un taux d'intérêt de {taux_interet}%."
        )
        
        actions = [
            {
                'type': 'primary',
                'label': 'Accepter le prêt',
                'url': f'/prets/{pret.id}/accepter/',
                'method': 'POST',
                'confirm': f'Accepter le prêt de {montant} FCFA ?'
            },
            {
                'type': 'secondary',
                'label': 'Voir les détails',
                'url': f'/prets/{pret.id}/',
                'method': 'GET'
            }
        ]
        
        donnees_supplementaires = {
            'pret_id': pret.id,
            'montant': montant,
            'taux_interet': taux_interet,
            'type_action': 'acceptation_pret'
        }
        
        return NotificationService.creer_notification(
            utilisateur=client,
            titre=titre,
            message=message,
            objet_lie=pret,
            donnees_supplementaires=donnees_supplementaires,
            actions=actions
        )
    
    @staticmethod
    def creer_notification_mobile_money_reussi(
        client,
        transaction: Any,
        montant: float,
        type_operation: str
    ) -> Notification:
        """
        Crée une notification pour une transaction Mobile Money réussie.
        """
        titre = "Transaction réussie"
        message = (
            f"Votre {type_operation} de {montant} FCFA via Mobile Money "
            f"a été effectuée avec succès."
        )
        
        actions = [
            {
                'type': 'info',
                'label': 'Voir le reçu',
                'url': f'/mobile-money/recu/{transaction.id}/',
                'method': 'GET'
            }
        ]
        
        donnees_supplementaires = {
            'transaction_id': transaction.id,
            'montant': montant,
            'type_operation': type_operation,
            'type_action': 'voir_recu'
        }
        
        return NotificationService.creer_notification(
            utilisateur=client,
            titre=titre,
            message=message,
            objet_lie=transaction,
            donnees_supplementaires=donnees_supplementaires,
            actions=actions
        )
    
    @staticmethod
    def envoyer_notification(notification: Notification) -> bool:
        """
        Envoie une notification via le canal spécifié.
        """
        try:
            # Simulation d'envoi pour l'instant
            success = True
            
            if notification.canal == 'email':
                # TODO: Implémenter envoi d'email
                logger.info(f"Simulation envoi email pour notification {notification.id}")
                success = True
            elif notification.canal == 'app':
                # Notification déjà stockée en base, pas d'envoi externe nécessaire
                success = True
            
            if success:
                notification.envoye = True
                notification.date_envoi = timezone.now()
                notification.save(update_fields=['envoye', 'date_envoi'])
                logger.info(f"Notification {notification.id} marquée comme envoyée")
            
            return success
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de notification {notification.id}: {str(e)}")
            return False
    
    @staticmethod
    def envoyer_notifications_en_masse(
        utilisateurs,
        titre: str,
        message: str,
        canal: str = 'app',
        donnees_supplementaires: Dict = None,
        actions: List[Dict] = None
    ) -> List[Notification]:
        """
        Envoie une notification à plusieurs utilisateurs.
        """
        notifications = []
        
        for utilisateur in utilisateurs:
            try:
                notification = NotificationService.creer_notification(
                    utilisateur=utilisateur,
                    titre=titre,
                    message=message,
                    canal=canal,
                    donnees_supplementaires=donnees_supplementaires,
                    actions=actions
                )
                notifications.append(notification)
            except Exception as e:
                logger.error(f"Erreur lors de la création de notification pour {utilisateur.username}: {str(e)}")
        
        return notifications








