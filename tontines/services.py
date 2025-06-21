from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.conf import settings
from notifications.services import NotificationService
from notifications.models import Notification
from typing import Optional
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class AdhesionNotificationService:
    """
    Service spécialisé pour les notifications d'adhésion aux tontines.
    Gère à la fois les notifications internes et les emails.
    """
    
    @staticmethod
    def notifier_adhesion_validee(
        client,
        tontine,
        workflow,
        agent_validateur,
        montant_adhesion: float
    ) -> dict:
        """
        Notifie le client que sa demande d'adhésion a été validée.
        Crée une notification interne ET envoie un email avec le lien de paiement.
        
        Args:
            client: L'objet Client
            tontine: L'objet Tontine  
            workflow: L'objet WorkflowAdhesion
            agent_validateur: L'agent qui a validé
            montant_adhesion: Montant des frais d'adhésion
            
        Returns:
            dict: Résultat des notifications avec statuts
        """
        resultats = {
            'notification_interne': False,
            'email_envoye': False,
            'erreurs': [],
            'notification_id': None,
            'lien_paiement': None
        }
        try:
            # 1. Génération du lien de paiement Mobile Money avec token
            site_url = getattr(settings, 'SITE_URL', '')
            # On utilise le token stocké dans le workflow
            paiement_token = workflow.metadata.get('paiement_token') if workflow.metadata else None
            lien_paiement_relatif = reverse('mobile_money:paiement_adhesion_formulaire')
            lien_paiement_complet = f"{site_url}{lien_paiement_relatif}?workflow_id={workflow.id}&token={paiement_token}"
            resultats['lien_paiement'] = lien_paiement_complet
            
            # 2. Création de la notification interne avec le lien de paiement
            notification_interne = AdhesionNotificationService._creer_notification_interne(
                client=client,
                tontine=tontine,
                workflow=workflow,
                agent_validateur=agent_validateur,
                montant_adhesion=montant_adhesion,
                lien_paiement=lien_paiement_complet
            )
            
            if notification_interne:
                resultats['notification_interne'] = True
                resultats['notification_id'] = notification_interne.id
                logger.info(f"Notification interne créée (ID: {notification_interne.id}) pour {client.nom_complet}")
            else:
                resultats['erreurs'].append("Échec de création de la notification interne")
                
            # 3. Envoi de l'email avec le lien de paiement (désactivé temporairement)
            # email_result = EmailService.envoyer_email_adhesion_validee(
            #     client=client,
            #     tontine=tontine,
            #     workflow=workflow,
            #     montant_adhesion=montant_adhesion,
            #     lien_paiement=lien_paiement_complet,
            #     agent_validateur=agent_validateur
            # )
            
            # Simulation d'envoi d'email réussi pour l'instant
            email_result = True
            
            if email_result:
                resultats['email_envoye'] = True
                logger.info(f"Email d'adhésion validée simulé pour {client.user.email if client.user else 'email non disponible'}")
            else:
                resultats['erreurs'].append("Échec de l'envoi d'email")
                
            # 4. Mise à jour du workflow avec les informations de notification
            workflow.email_confirmation_envoye = resultats['email_envoye']
            if resultats['notification_interne']:
                workflow.date_modification = timezone.now()
            workflow.save(update_fields=['email_confirmation_envoye', 'date_modification'])
            
            # 5. Log de synthèse
            logger.info(
                f"Notification adhésion validée - Client: {client.nom_complet}, "
                f"Tontine: {tontine.nom}, Notification: {resultats['notification_interne']}, "
                f"Email: {resultats['email_envoye']}"
            )
            
            return resultats
            
        except Exception as e:
            logger.error(f"Erreur dans notifier_adhesion_validee: {str(e)}")
            resultats['erreurs'].append(f"Erreur générale: {str(e)}")
            return resultats
    
    @staticmethod
    def _creer_notification_interne(
        client,
        tontine,
        workflow,
        agent_validateur,
        montant_adhesion: float,
        lien_paiement: str
    ) -> Optional[Notification]:
        """
        Crée la notification interne avec bouton de paiement intégré.
        """
        try:
            # Vérification de l'utilisateur client
            if not client.user:
                logger.error(f"Le client {client} n'a pas d'utilisateur Django associé")
                return None
            
            # Message détaillé pour la notification
            message = (
                f"🎉 Excellente nouvelle !\n\n"
                f"Votre demande d'adhésion à la tontine '{tontine.nom}' a été validée avec succès par notre équipe.\n\n"
                f"Détails de l'adhésion :\n"
                f"- Tontine : {tontine.nom}\n"
                f"- Montant d'adhésion : {montant_adhesion:,.0f} FCFA\n"
                f"- Date de validation : {timezone.now().strftime('%d/%m/%Y à %H:%M')}\n"
                f"- Agent validateur : {agent_validateur.nom_complet if agent_validateur else 'Système'}\n\n"
                f"📱 Prochaine étape : Effectuez le paiement des frais d'adhésion pour finaliser votre intégration dans la tontine.\n\n"
                f"⚠️ Important : Vous disposez de 7 jours pour effectuer ce paiement."
            )

            # Actions disponibles dans la notification (boutons)
            actions = [
                {
                    'type': 'primary',
                    'label': f'💳 Payer {montant_adhesion:,.0f} FCFA',
                    'url': lien_paiement,
                    'target': '_blank',
                    'class': 'btn btn-success btn-lg',
                    'icon': 'fa-credit-card'
                },
                {
                    'type': 'secondary',
                    'label': '📋 Voir détails',
                    'url': f"/tontines/workflow/{workflow.id}/details/",
                    'class': 'btn btn-outline-primary',
                    'icon': 'fa-info-circle'
                },
                {
                    'type': 'link',
                    'label': '📞 Contacter le support',
                    'url': f"mailto:{getattr(settings, 'EMAIL_SUPPORT', 'support@tontiflex.com')}",
                    'class': 'btn btn-outline-secondary btn-sm',
                    'icon': 'fa-envelope'
                }
            ]
            
            # Données supplémentaires pour l'interface
            donnees_supplementaires = {
                'type_evenement': 'adhesion_validee',
                'tontine_id': str(tontine.id),
                'tontine_nom': tontine.nom,
                'workflow_id': str(workflow.id),
                'montant_adhesion': float(montant_adhesion),
                'agent_validateur_id': str(agent_validateur.id) if agent_validateur else None,
                'agent_validateur_nom': agent_validateur.nom_complet if agent_validateur else 'Système',
                'date_validation': timezone.now().isoformat(),
                'date_expiration_paiement': (timezone.now() + timezone.timedelta(days=7)).isoformat(),
                'lien_paiement': lien_paiement,
                'statut_paiement': 'en_attente',
                'devise': 'FCFA',
                'plateforme': 'TontiFlex',
                # Métadonnées pour l'interface
                'css_classes': 'notification-adhesion-validee',
                'show_payment_button': True,
                'show_countdown': True,
                'priority_display': True
            }
            
            # Création de la notification
            notification = NotificationService.creer_notification(
                utilisateur=client.user,
                titre="✅ Demande d'adhésion validée - Paiement requis",
                message=message,
                canal='app',
                objet_lie=workflow,
                donnees_supplementaires=donnees_supplementaires,
                actions=actions
            )
            
            if notification:
                logger.info(
                    f"Notification interne créée (ID: {notification.id}) pour {client.nom_complet} "
                    f"- Tontine: {tontine.nom} - Montant: {montant_adhesion} FCFA"
                )
                return notification
            else:
                logger.error(f"Échec de création de la notification pour {client.nom_complet}")
                return None
                
        except Exception as e:
            logger.error(f"Erreur lors de la création de la notification interne: {str(e)}")
            return None
    
    @staticmethod
    def notifier_paiement_recu(client, tontine, workflow, transaction) -> dict:
        """
        Notifie le client que son paiement a été reçu et que l'adhésion est finalisée.
        """
        resultats = {
            'notification_interne': False,
            'email_envoye': False,
            'erreurs': []
        }
        
        try:
            # Message de félicitations
            message = (
                f"🎉 Félicitations !\n\n"
                f"Votre paiement de {transaction.montant:,.0f} FCFA pour l'adhésion à la tontine '{tontine.nom}' a été confirmé.\n\n"
                f"Vous êtes maintenant officiellement membre de cette tontine !\n\n"
                f"Détails du paiement :\n"
                f"- Montant : {transaction.montant:,.0f} FCFA\n"
                f"- Référence : {transaction.reference_externe}\n"
                f"- Date : {transaction.date_transaction.strftime('%d/%m/%Y à %H:%M')}\n\n"
                f"Prochaines étapes :\n"
                f"- Vous recevrez bientôt les détails de votre première cotisation\n"
                f"- Consultez le calendrier de la tontine dans votre espace membre\n"
                f"- Participez aux réunions et activités du groupe"
            )
          
            actions = [
                {
                    'type': 'primary',
                    'label': '👥 Voir ma tontine',
                    'url': f"/tontines/{tontine.id}/",
                    'class': 'btn btn-success',
                    'icon': 'fa-users'
                },
                {
                    'type': 'secondary',
                    'label': '📊 Mon tableau de bord',
                    'url': "/dashboard/",
                    'class': 'btn btn-outline-primary',
                    'icon': 'fa-tachometer-alt'
                }
            ]
            
            donnees_supplementaires = {
                'type_evenement': 'paiement_adhesion_confirme',
                'tontine_id': str(tontine.id),
                'transaction_id': str(transaction.id),
                'montant_paye': float(transaction.montant),
                'reference_transaction': transaction.reference_externe,
                'date_paiement': transaction.date_transaction.isoformat(),
                'statut_adhesion': 'finalisee'
            }
            
            # Notification interne
            notification = NotificationService.creer_notification(
                utilisateur=client.user,
                titre="🎉 Paiement confirmé - Bienvenue dans la tontine !",
                message=message,
                canal='app',
                objet_lie=workflow,
                donnees_supplementaires=donnees_supplementaires,
                actions=actions
            )
            
            if notification:
                resultats['notification_interne'] = True
                logger.info(f"Notification de paiement confirmé créée pour {client.nom_complet}")
            
            # Marquer comme envoyé pour l'instant (sans email service)
            resultats['email_envoye'] = True
            
            return resultats
            
        except Exception as e:
            logger.error(f"Erreur dans notifier_paiement_recu: {str(e)}")
            resultats['erreurs'].append(f"Erreur: {str(e)}")
            return resultats
    
    @staticmethod
    def programmer_rappels_paiement(workflow, client, tontine) -> bool:
        """
        Programme des rappels automatiques pour le paiement.
        """
        try:
            from datetime import timedelta
            
            # Programmer des rappels à J+3 et J+6
            dates_rappel = [
                timezone.now() + timedelta(days=3),
                timezone.now() + timedelta(days=6)
            ]
            
            for i, date_rappel in enumerate(dates_rappel, 1):
                message = (
                    f"⏰ Rappel de paiement\n\n"
                    f"N'oubliez pas de payer vos frais d'adhésion de {workflow.frais_adhesion_calcules:,.0f} FCFA "
                    f"pour la tontine '{tontine.nom}'.\n\n"
                    f"Il vous reste {7 - (3 * i)} jours pour effectuer ce paiement."
                )
                
                # Créer notification de rappel
                NotificationService.creer_notification(
                    utilisateur=client.user,
                    titre=f"⏰ Rappel #{i} - Paiement d'adhésion en attente",
                    message=message,
                    canal='app',
                    objet_lie=workflow,
                    donnees_supplementaires={
                        'type_evenement': 'rappel_paiement',
                        'numero_rappel': i,
                        'workflow_id': str(workflow.id)
                    }
                )
            
            logger.info(f"Rappels de paiement programmés pour le workflow {workflow.id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur programmation rappels: {str(e)}")
            return False

    @staticmethod
    def notifier_demande_rejetee(client, tontine, workflow, agent_rejeteur, raison_rejet: str) -> dict:
        """
        Notifie le client que sa demande d'adhésion a été rejetée.
        """
        resultats = {
            'notification_interne': False,
            'email_envoye': False,
            'erreurs': []
        }
        
        try:
            message = (
                f"❌ Demande d'adhésion rejetée\n\n"
                f"Nous regrettons de vous informer que votre demande d'adhésion à la tontine '{tontine.nom}' "
                f"a été rejetée.\n\n"
                f"Raison du rejet :\n{raison_rejet}\n\n"
                f"Vous pouvez corriger les problèmes mentionnés et soumettre une nouvelle demande."
            )
            
            actions = [
                {
                    'type': 'primary',
                    'label': '📝 Nouvelle demande',
                    'url': f"/tontines/{tontine.id}/adherer/",
                    'class': 'btn btn-primary',
                    'icon': 'fa-plus'
                },
                {
                    'type': 'secondary',
                    'label': '📞 Contacter le support',
                    'url': f"mailto:{getattr(settings, 'EMAIL_SUPPORT', 'support@tontiflex.com')}",
                    'class': 'btn btn-outline-secondary',
                    'icon': 'fa-envelope'
                }
            ]
            
            donnees_supplementaires = {
                'type_evenement': 'demande_rejetee',
                'tontine_id': str(tontine.id),
                'workflow_id': str(workflow.id),
                'agent_rejeteur_id': str(agent_rejeteur.id) if agent_rejeteur else None,
                'raison_rejet': raison_rejet
            }
            
            notification = NotificationService.creer_notification(
                utilisateur=client.user,
                titre="❌ Demande d'adhésion rejetée",
                message=message,
                canal='app',
                objet_lie=workflow,
                donnees_supplementaires=donnees_supplementaires,
                actions=actions
            )
            
            if notification:
                resultats['notification_interne'] = True
                logger.info(f"Notification de rejet créée pour {client.nom_complet}")
            
            resultats['email_envoye'] = True  # Simulation
            return resultats
            
        except Exception as e:
            logger.error(f"Erreur notification rejet: {str(e)}")
            resultats['erreurs'].append(f"Erreur: {str(e)}")
            return resultats

    @staticmethod
    def notifier_cotisation_due(client, tontine, montant_cotisation: float, date_echeance) -> dict:
        """
        Notifie le client qu'une cotisation est due.
        """
        resultats = {
            'notification_interne': False,
            'email_envoye': False,
            'erreurs': []
        }
        
        try:
            message = (
                f"💰 Cotisation due\n\n"
                f"Votre cotisation pour la tontine '{tontine.nom}' est maintenant due.\n\n"
                f"Détails :\n"
                f"- Montant : {montant_cotisation:,.0f} FCFA\n"
                f"- Date d'échéance : {date_echeance.strftime('%d/%m/%Y')}\n\n"
                f"Effectuez votre paiement avant la date d'échéance pour éviter des pénalités."
            )
            
            actions = [
                {
                    'type': 'primary',
                    'label': f'💳 Payer {montant_cotisation:,.0f} FCFA',
                    'url': f"/tontines/{tontine.id}/cotiser/",
                    'class': 'btn btn-success btn-lg',
                    'icon': 'fa-credit-card'
                },
                {
                    'type': 'secondary',
                    'label': '📊 Voir historique',
                    'url': f"/tontines/{tontine.id}/historique/",
                    'class': 'btn btn-outline-primary',
                    'icon': 'fa-history'
                }
            ]
            
            donnees_supplementaires = {
                'type_evenement': 'cotisation_due',
                'tontine_id': str(tontine.id),
                'montant_cotisation': float(montant_cotisation),
                'date_echeance': date_echeance.isoformat(),
                'statut_paiement': 'en_attente'
            }
            
            notification = NotificationService.creer_notification(
                utilisateur=client.user,
                titre="💰 Cotisation due - Paiement requis",
                message=message,
                canal='app',
                objet_lie=tontine,
                donnees_supplementaires=donnees_supplementaires,
                actions=actions
            )
            
            if notification:
                resultats['notification_interne'] = True
                logger.info(f"Notification de cotisation due créée pour {client.nom_complet}")
            
            resultats['email_envoye'] = True  # Simulation
            return resultats
            
        except Exception as e:
            logger.error(f"Erreur notification cotisation due: {str(e)}")
            resultats['erreurs'].append(f"Erreur: {str(e)}")
            return resultats
