# -*- coding: utf-8 -*-
"""
Service d'adhésion Mobile Money avec corrections pour les logs et validation.
Version corrigée : suppression des emojis et amélioration de la validation.
"""

import logging
import uuid
from decimal import Decimal, ROUND_UP
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

class AdhesionMobileMoneyService:
    """Service pour gérer les adhésions via Mobile Money."""
    
    def __init__(self):
        self.operateur = 'MTN' 
        
    def generer_paiement_adhesion(self, workflow, numero_telephone, force_ussd=False):
        """
        Génère un paiement d'adhésion via Mobile Money (MTN API officielle).
        """
        try:
            from mobile_money.services_mtn_new_api_complete import MTNConformeAPIService
            montant = getattr(workflow, 'frais_adhesion_calcules', None) or getattr(workflow, 'fraisAdhesion', None)
            if montant is None:
                montant = getattr(workflow, 'tontine', None) and getattr(workflow.tontine, 'fraisAdhesion', None)
            if montant is None:
                raise Exception("Impossible de déterminer le montant des frais d'adhésion.")
            montant = Decimal(str(montant))
            reference = f"ADH_{workflow.id}_{int(timezone.now().timestamp())}"
            service = MTNConformeAPIService()
            result = service.initier_paiement_conforme(
                numero_telephone=numero_telephone,
                montant=montant,
                reference_externe=reference,
                description="Frais d'adhésion tontine"
            )
            # Ici, tu peux créer la transaction Mobile Money en base si besoin, ou retourner le résultat MTN
            return {
                'success': True,
                'reference_interne': reference,
                'resultat_mtn': result,
                'montant': float(montant),
                'message': 'Paiement d\'adhésion initié via MTN MoMo API officielle'
            }
        except Exception as e:
            logger.error(f"[ADHESION] Erreur lors de la génération du paiement: {str(e)}")
            return {
                'success': False,
                'error': f'Erreur lors de la génération du paiement: {str(e)}'
            }
    
    def traiter_confirmation_paiement(self, reference_interne, statut_paiement, donnees_callback):
        """
        Traite la confirmation de paiement d'adhésion.
        Version corrigée avec logs sans emojis.
        """
        try:
            # Log de début sans emoji
            logger.info(f"[ADHESION] Traitement confirmation - Référence: {reference_interne}")
            print(f"[INFO] Traitement confirmation paiement: {reference_interne}")
            
            if statut_paiement == 'succes':
                # Log de succès sans emoji
                logger.info(f"[ADHESION] Paiement confirmé avec succès - Référence: {reference_interne}")
                print(f"[SUCCES] Confirmation paiement d'adhésion réussie")
                
                return {
                    'success': True,
                    'message': 'Paiement d\'adhésion confirmé avec succès'
                }
            else:
                # Log d'échec sans emoji
                logger.warning(f"[ADHESION] Paiement échoué - Référence: {reference_interne}")
                print(f"[ECHEC] Confirmation paiement d'adhésion échouée")
                
                return {
                    'success': False,
                    'error': 'Paiement d\'adhésion échoué'                }
                
        except Exception as e:
            # Log d'erreur sans emoji
            logger.error(f"[ADHESION] Erreur traitement confirmation: {str(e)}")
            print(f"[ERREUR] Erreur traitement confirmation: {str(e)}")
            
            return {
                'success': False,
                'error': f'Erreur lors du traitement de la confirmation: {str(e)}'
            }

    def _creer_transaction_adhesion(self, workflow, reference_interne, montant, numero_telephone, operateur):
        """
        Crée une transaction Mobile Money en base de données pour l'adhésion.
        """
        from mobile_money.models import TransactionMobileMoney, OperateurMobileMoney
        
        try:
            # Obtenir ou créer l'opérateur MTN
            operateur_obj, created = OperateurMobileMoney.objects.get_or_create(
                code=operateur,
                defaults={
                    'nom': f'{operateur} Mobile Money',
                    'prefixes_telephone': ['2290196', '2290197', '2290161', '2290162', '2290166', '2290167', '2290169', '2290151', '2290152', '2290190'],
                    'api_base_url': 'https://sandbox.api.mtn.com',
                    'statut': 'actif'
                }
            )
            
            # Créer la transaction Mobile Money
            transaction = TransactionMobileMoney.objects.create(
                reference_interne=reference_interne,
                reference_operateur=f"OP_{reference_interne}",
                type_transaction='paiement',
                montant=montant,
                frais=Decimal('0.00'),
                montant_total=montant,
                numero_telephone=numero_telephone,
                nom_client=workflow.demande_adhesion.client.nom,
                statut='initie',
                operateur=operateur_obj,
                client=workflow.demande_adhesion.client,
                description=f"Paiement d'adhésion à la tontine {workflow.demande_adhesion.tontine.nom}",
                metadata={
                    'workflow_id': str(workflow.id),
                    'tontine_id': str(workflow.demande_adhesion.tontine.id),
                    'type_paiement': 'adhesion'
                }
            )
            
            logger.info(f"[ADHESION] Transaction Mobile Money créée - ID: {transaction.id}")
            return transaction
            
        except Exception as e:
            logger.error(f"[ADHESION] Erreur création transaction: {str(e)}")
            raise
