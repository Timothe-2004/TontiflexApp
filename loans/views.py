"""
VUES ET ENDPOINTS REST POUR LE MODULE PRÊTS - TONTIFLEX

Ce module contient tous les ViewSets et endpoints pour:
1. Gestion des demandes de prêt (CRUD + workflow)
2. Workflow Superviseur → Admin obligatoire
3. Conditions de remboursement et calculs
4. Gestion des prêts accordés et décaissements
5. Échéances et remboursements
6. Rapports et statistiques

Respect strict des permissions par rôle et des règles métier
"""

import logging
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.http import Http404, FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from .models import LoanApplication, LoanTerms, Loan, RepaymentSchedule, Payment
from .serializers import (
    LoanApplicationSerializer, LoanTermsSerializer, LoanSerializer,
    RepaymentScheduleSerializer, PaymentSerializer,
    EligibilityCheckSerializer, EligibilityResponseSerializer,
    ExaminerDemandeSerializer, DefinirConditionsSerializer,
    TransfererAdminSerializer, ValidationAdminSerializer,
    MarquerDecaisseSerializer, EffectuerRemboursementSerializer,
    ScoreFiabiliteSerializer, CalendrierRemboursementSerializer,
    LoanApplicationResponseSerializer, StatistiquesPretsSerializer,
    RapportDemandeSerializer, ExportDemandesSerializer
)
from .permissions import (
    IsClientOwner, IsSuperviseurSFD, IsAdminSFD, IsAdminPlateforme,
    CanExamineLoanApplication, CanDefineTerms, CanTransferToAdmin,
    CanFinalApprove, CanMarkDisbursed, CanMakeRepayment, CanViewCreditScore,
    LoanApplicationPermission, LoanPermission
)
from .utils import (
    calculer_score_fiabilite_client, analyser_capacite_remboursement,
    generer_rapport_demande, calculer_statistiques_prets,
    calculer_tableau_amortissement
)
from .tasks import (
    envoyer_notification_demande_soumise, envoyer_notification_demande_traitee,
    calculer_penalites_quotidiennes, envoyer_rappels_echeances
)

logger = logging.getLogger(__name__)


# =============================================================================
# DEMANDES DE PRÊT
# =============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="Liste des demandes de prêt",
        description="""
        Récupère la liste des demandes de prêt selon les permissions utilisateur.
        
        Processus de demande de prêt TontiFlex:
        1. Client soumet une demande avec documents justificatifs PDF
        2. Vérification automatique d'éligibilité (compte épargne > 3 mois)
        3. Calcul du score de fiabilité basé sur l'historique
        4. Traitement par Superviseur SFD (définir conditions)
        5. Transfert OBLIGATOIRE vers Admin SFD pour validation finale
        6. Décaissement en personne après accord final
        7. Génération du calendrier de remboursement
        8. Suivi des échéances et remboursements Mobile Money
        
        Statuts de demande:
        soumis: Demande créée par le client, en attente de traitement superviseur
        examine_superviseur: En cours d'examen par le superviseur SFD
        transfere_admin: Conditions définies, transférée vers admin pour validation
        accorde: Validée par admin SFD, prêt créé et prêt au décaissement
        rejete: Refusée soit par superviseur soit par admin (avec motif)
        
        Éligibilité requise:
        Compte épargne actif depuis au moins 3 mois
        Aucun prêt en cours (un seul prêt autorisé à la fois)
        Documents justificatifs valides (revenus, garanties)
        Score de fiabilité minimum calculé automatiquement
        """,
        responses={200: LoanApplicationSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Créer une demande de prêt",
        description="""
        Permet à un client de créer une nouvelle demande de prêt.
        
        Conditions d'éligibilité automatiquement vérifiées:
        Client avec compte épargne actif depuis au moins 3 mois
        Aucun prêt en cours ou impayé
        Documents d'identité et justificatifs valides
        Capacité de remboursement démontrée
        
        Documents requis (PDF uniquement):
        Justificatifs de revenus (bulletins salaire, relevés activité)
        Garanties ou avals (si montant > seuil SFD)
        Plan d'utilisation des fonds détaillé
        Références commerciales ou professionnelles
        
        Calculs automatiques:
        Score de fiabilité basé sur historique épargne et tontines
        Capacité de remboursement analysée
        Recommandations de montant et durée
        
        Workflow après création:
        1. Statut initial: soumis
        2. Notification automatique au superviseur SFD
        3. Attente d'examen et définition des conditions
        """,
        request=LoanApplicationSerializer,
        responses={
            201: LoanApplicationSerializer,
            400: OpenApiResponse(description="Données invalides ou client non éligible"),
            409: OpenApiResponse(description="Client a déjà un prêt en cours")
        },
        examples=[
            OpenApiExample(
                "Demande de prêt commerce",
                value={
                    "montant_souhaite": 500000,
                    "duree_souhaitee_mois": 12,
                    "motif": "Extension commerce de détail",
                    "justificatifs_revenus": "base64_encoded_pdf_data",
                    "plan_utilisation": "Achat stock marchandises et rénovation boutique",
                    "garanties_proposees": "Caution solidaire + nantissement matériel",
                    "revenus_mensuels_declares": 200000,
                    "charges_mensuelles": 80000
                }
            ),
            OpenApiExample(
                "Demande de prêt agriculture",
                value={
                    "montant_souhaite": 300000,
                    "duree_souhaitee_mois": 18,
                    "motif": "Campagne agricole saison sèche",
                    "justificatifs_revenus": "base64_encoded_pdf_data",
                    "plan_utilisation": "Achat semences, engrais et location tracteur",
                    "garanties_proposees": "Hypothèque sur terrain agricole",
                    "revenus_mensuels_declares": 150000,
                    "charges_mensuelles": 60000
                }
            )
        ]
    ),
    retrieve=extend_schema(
        summary="Détails d'une demande de prêt",
        description="""
        Récupère les informations détaillées d'une demande de prêt spécifique.
        
        Informations affichées:
        Données complètes de la demande du client
        Score de fiabilité calculé avec détails
        Historique du traitement (superviseur → admin)
        Conditions de remboursement si définies
        Documents joints et justificatifs
        Commentaires et décisions des agents
        
        Permissions:
        Client: Peut voir uniquement ses propres demandes
        Superviseur SFD: Demandes des clients de sa SFD
        Admin SFD: Demandes transférées de sa SFD
        Admin Plateforme: Toutes les demandes
        """
    ),
    update=extend_schema(
        summary="Modifier une demande de prêt",
        description="""
        Met à jour une demande de prêt existante.
        
        Modifications autorisées:
        Client: Peut modifier uniquement les demandes en statut 'soumis'
        Superviseur: Peut modifier statut et ajouter commentaires
        Admin SFD: Peut modifier statut final et conditions
        
        Champs modifiables par le client:
        Montant souhaité et durée
        Motif et plan d'utilisation
        Documents justificatifs (remplacement)
        Garanties proposées
        
        Restrictions:
        Aucune modification après accord final
        Certains champs verrouillés selon le statut
        Traçabilité complète des modifications
        """
    ),
    partial_update=extend_schema(
        summary="Modification partielle d'une demande",
        description="Met à jour partiellement une demande de prêt (uniquement les champs fournis)."
    ),
    destroy=extend_schema(
        summary="Supprimer une demande de prêt",
        description="""
        Supprime définitivement une demande de prêt.
        
        Conditions de suppression:
        Demande en statut 'soumis' uniquement
        Seul le client demandeur peut supprimer
        Admins peuvent supprimer demandes non accordées
        
        Effets: Suppression complète, pas de récupération possible
        """
    )
)
@extend_schema(tags=["💰 Demandes de Prêt"])
class LoanApplicationViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des demandes de prêt.
    
    Permissions:
    - Client: Créer et voir ses propres demandes
    - Superviseur SFD: Voir et traiter les demandes de ses clients
    - Admin SFD: Voir et approuver les demandes transférées
    - Admin Plateforme: Accès complet
    """
    serializer_class = LoanApplicationSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.type_utilisateur == 'client':
            # Client ne voit que ses propres demandes
            return LoanApplication.objects.filter(client=user).order_by('-date_soumission')
        
        elif user.type_utilisateur == 'superviseur_sfd':
            # Superviseur voit les demandes des clients de sa SFD
            return LoanApplication.objects.filter(
                client__compte_epargne__agent_validateur__sfd=user.sfd
            ).order_by('-date_soumission')
        
        elif user.type_utilisateur == 'admin_sfd':
            # Admin SFD voit les demandes transférées de sa SFD
            return LoanApplication.objects.filter(
                client__compte_epargne__agent_validateur__sfd=user.sfd
            ).order_by('-date_soumission')
        
        elif user.type_utilisateur == 'admin_plateforme':
            # Admin plateforme voit tout
            return LoanApplication.objects.all().order_by('-date_soumission')
        
        return LoanApplication.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return LoanApplicationSerializer
        elif self.action in ['retrieve', 'list']:
            return LoanApplicationSerializer
        return self.serializer_class
    
    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        elif self.action in ['retrieve', 'list']:
            return [LoanApplicationPermission()]
        elif self.action in ['process_application', 'transfer_to_admin']:
            return [LoanApplicationPermission()]
        return [permissions.IsAuthenticated()]
    
    def perform_create(self, serializer):
        """Créer une nouvelle demande de prêt."""
        try:
            # Vérifier l'éligibilité automatiquement
            client = self.request.user
            
            # Vérifier que le client a un compte épargne actif > 3 mois
            if not hasattr(client, 'compte_epargne') or client.compte_epargne.statut != 'actif':
                raise ValidationError("Vous devez avoir un compte épargne actif pour demander un prêt.")
            
            anciennete_jours = (timezone.now() - client.compte_epargne.date_activation).days
            if anciennete_jours < 90:  # 3 mois
                raise ValidationError("Votre compte épargne doit être actif depuis au moins 3 mois.")
            
            # Vérifier qu'il n'y a pas de prêt en cours
            pret_en_cours = Loan.objects.filter(
                client=client,
                statut__in=['accorde', 'decaisse', 'en_remboursement']
            ).exists()
            
            if pret_en_cours:
                raise ValidationError("Vous avez déjà un prêt en cours. Un seul prêt est autorisé à la fois.")
            
            # Calculer le score de fiabilité
            score_info = calculer_score_fiabilite_client(client)
            
            # Sauvegarder la demande
            demande = serializer.save(
                client=client,
                score_fiabilite=Decimal(str(score_info['score'])),
                details_score=score_info,
                statut='soumis'
            )
            
            # Envoyer notification asynchrone
            envoyer_notification_demande_soumise.delay(demande.id)
            
            logger.info(f"Nouvelle demande de prêt créée: {demande.id} pour client {client.id}")
            
        except Exception as e:
            logger.error(f"Erreur création demande de prêt: {e}")
            raise ValidationError(str(e))
    
    @extend_schema(
        summary="Traiter une demande de prêt (Superviseur SFD)",
        description="""
        Permet à un superviseur SFD d'examiner et traiter une demande de prêt.
        
        **Rôle du Superviseur SFD**:
        - Analyse de la demande et des documents fournis
        - Évaluation de la capacité de remboursement du client
        - Définition des conditions de prêt (montant, taux, durée)
        - Décision d'approbation ou de rejet avec justification
        - Transfert OBLIGATOIRE vers Admin SFD si approuvé
        
        **Processus d'examen**:
        1. Vérification des documents justificatifs
        2. Analyse du score de fiabilité calculé
        3. Évaluation des garanties proposées
        4. Définition des conditions personnalisées
        5. Transfert automatique vers admin pour validation finale
        
        **Actions possibles**:
        - Approuver: Définir conditions et transférer à l'admin
        - Rejeter: Refus définitif avec motif détaillé
        - Demander compléments: Retour au client pour documents additionnels
        
        **Conditions requises**:
        - Statut de la demande: 'soumis'
        - Utilisateur: Superviseur SFD de la même SFD que le client
        - Documents justificatifs complets et valides
        
        **Workflow après traitement**:
        Si approuvé: Statut → 'transfere_admin', notification à l'admin SFD
        Si rejeté: Statut → 'rejete', notification au client avec motif
        """,
        request=ExaminerDemandeSerializer,
        responses={
            200: LoanApplicationResponseSerializer,
            400: OpenApiResponse(description="Erreur de validation ou demande non traitable"),
            403: OpenApiResponse(description="Permissions insuffisantes"),
            404: OpenApiResponse(description="Demande introuvable")
        },
        examples=[
            OpenApiExample(
                "Approbation avec conditions",
                value={
                    "action": "approuver",
                    "commentaire": "Dossier complet, client fiable avec bon historique épargne",
                    "montant_accorde": 400000,
                    "taux_interet": 12.5,
                    "duree_mois": 12,
                    "conditions_particulieres": "Remboursement anticipé autorisé sans pénalité"
                }
            ),
            OpenApiExample(
                "Rejet motivé",
                value={
                    "action": "rejeter",
                    "commentaire": "Capacité de remboursement insuffisante, revenus irréguliers",
                    "recommandations": "Développer activité sur 6 mois puis renouveler demande"
                }
            )
        ]
    )
    @action(detail=True, methods=['post'], url_path='process-application')
    def process_application(self, request, pk=None):
        """Traiter une demande de prêt (Superviseur SFD uniquement)."""
        demande = self.get_object()
        action = request.data.get('action')
        
        # Vérifications
        if demande.statut != 'soumis':
            return Response(
                {'erreur': 'Cette demande ne peut plus être traitée'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if request.user.type_utilisateur != 'superviseur_sfd':
            return Response(
                {'erreur': 'Seul un superviseur SFD peut traiter les demandes'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            with transaction.atomic():
                if action == 'rejeter':
                    # Rejet direct par le superviseur
                    demande.statut = 'rejete'
                    demande.commentaire_superviseur = request.data.get('commentaire', '')
                    demande.date_traitement_superviseur = timezone.now()
                    demande.superviseur_traitant = request.user
                    demande.save()
                    
                    # Notification
                    envoyer_notification_decision_pret.delay(
                        demande.id, 'rejete', demande.commentaire_superviseur
                    )
                    
                    return Response({
                        'message': 'Demande rejetée avec succès',
                        'demande': LoanApplicationDetailSerializer(demande).data
                    })
                
                elif action == 'approuver':
                    # Traitement par le superviseur - Création des conditions
                    montant_accorde = request.data.get('montant_accorde')
                    taux_interet = request.data.get('taux_interet')
                    duree_mois = request.data.get('duree_mois')
                    
                    if not all([montant_accorde, taux_interet, duree_mois]):
                        return Response(
                            {'erreur': 'Montant accordé, taux d\'intérêt et durée requis'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    # Validation des montants
                    montant_accorde = Decimal(str(montant_accorde))
                    if montant_accorde > demande.montant_souhaite:
                        return Response(
                            {'erreur': 'Le montant accordé ne peut pas dépasser le montant demandé'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    # Créer les conditions de remboursement
                    conditions = LoanTerms.objects.create(
                        demande=demande,
                        montant_accorde=montant_accorde,
                        taux_interet_annuel=Decimal(str(taux_interet)),
                        duree_mois=int(duree_mois),
                        definies_par=request.user
                    )
                    
                    # Mettre à jour la demande
                    demande.statut = 'transfere_admin'  # OBLIGATOIRE: Transfert vers admin
                    demande.commentaire_superviseur = request.data.get('commentaire', '')
                    demande.date_traitement_superviseur = timezone.now()
                    demande.superviseur_traitant = request.user
                    demande.save()
                    
                    logger.info(f"Demande {demande.id} traitée par superviseur et transférée à l'admin")
                    
                    return Response({
                        'message': 'Demande traitée et transférée à l\'administrateur pour validation finale',
                        'demande': LoanApplicationDetailSerializer(demande).data,
                        'conditions': LoanTermsSerializer(conditions).data
                    })
                
                else:
                    return Response(
                        {'erreur': 'Action non reconnue'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        except Exception as e:
            logger.error(f"Erreur traitement demande {pk}: {e}")
            return Response(
                {'erreur': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Validation finale Admin SFD",
        description="""
        Permet à un Admin SFD de valider définitivement une demande de prêt.
        
        **Rôle de l'Admin SFD**:
        - Validation finale après examen superviseur obligatoire
        - Vérification de la conformité réglementaire (UEMOA/BCEAO)
        - Autorisation de décaissement selon les fonds SFD disponibles
        - Création du contrat de prêt et du calendrier de remboursement
        - Signature électronique et archivage sécurisé
        
        **Processus de validation**:
        1. Revue des conditions définies par le superviseur
        2. Vérification de la disponibilité des fonds SFD
        3. Contrôle de conformité réglementaire
        4. Décision finale de validation ou rejet
        5. Création automatique du prêt si validé
        
        **Actions possibles**:
        - Valider: Création du prêt et calendrier de remboursement
        - Rejeter: Refus final avec motif réglementaire ou technique
        - Modifier conditions: Ajustement des conditions superviseur
        
        **Conditions requises**:
        - Statut de la demande: 'transfere_admin'
        - Utilisateur: Admin SFD de la même SFD
        - Conditions de remboursement préalablement définies
        - Fonds SFD suffisants pour le décaissement
        
        **Effets de la validation**:
        Si validé: Création d'un objet Loan, statut → 'accorde'
        Si rejeté: Statut → 'rejete', notification avec motif
        Génération automatique du contrat et calendrier
        """,
        request=ValidationAdminSerializer,
        responses={
            200: LoanApplicationResponseSerializer,
            400: OpenApiResponse(description="Erreur de validation ou fonds insuffisants"),
            403: OpenApiResponse(description="Permissions insuffisantes"),
            404: OpenApiResponse(description="Demande non transférée")
        },
        examples=[
            OpenApiExample(
                "Validation finale",
                value={
                    "action": "valider",
                    "commentaire": "Dossier conforme, fonds disponibles, contrat généré",
                    "ajustements_conditions": {
                        "taux_interet": 12.0,
                        "clauses_particulieres": "Assurance décès incluse"
                    }
                }
            ),
            OpenApiExample(
                "Rejet admin",
                value={
                    "action": "rejeter", 
                    "commentaire": "Fonds SFD insuffisants pour ce montant en ce moment",
                    "recommandations": "Renouveler la demande dans 2 mois"
                }
            )
        ]
    )
    @action(detail=True, methods=['post'], url_path='admin-decision')
    def admin_decision(self, request, pk=None):
        """Validation finale par l'Admin SFD."""
        demande = self.get_object()
        action = request.data.get('action')
        
        # Vérifications
        if demande.statut != 'transfere_admin':
            return Response(
                {'erreur': 'Cette demande n\'est pas en attente de validation admin'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if request.user.type_utilisateur != 'admin_sfd':
            return Response(
                {'erreur': 'Seul un admin SFD peut valider les demandes'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            with transaction.atomic():
                if action == 'rejeter':
                    # Rejet par l'admin
                    demande.statut = 'rejete'
                    demande.commentaire_admin = request.data.get('commentaire', '')
                    demande.date_traitement_admin = timezone.now()
                    demande.admin_validateur = request.user
                    demande.save()
                    
                    # Notification
                    envoyer_notification_decision_pret.delay(
                        demande.id, 'rejete', demande.commentaire_admin
                    )
                    
                    return Response({
                        'message': 'Demande rejetée par l\'administrateur',
                        'demande': LoanApplicationDetailSerializer(demande).data
                    })
                
                elif action == 'valider':
                    # Validation finale - Création du prêt
                    conditions = demande.conditions_remboursement
                    if not conditions:
                        return Response(
                            {'erreur': 'Aucune condition de remboursement définie'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    # Créer le prêt
                    pret = Loan.objects.create(
                        demande=demande,
                        client=demande.client,
                        montant_accorde=conditions.montant_accorde,
                        taux_interet_annuel=conditions.taux_interet_annuel,
                        duree_mois=conditions.duree_mois,
                        statut='accorde',
                        admin_validateur=request.user
                    )
                    
                    # Mettre à jour la demande
                    demande.statut = 'accorde'
                    demande.commentaire_admin = request.data.get('commentaire', '')
                    demande.date_traitement_admin = timezone.now()
                    demande.admin_validateur = request.user
                    demande.save()
                    
                    # Notification
                    envoyer_notification_decision_pret.delay(
                        demande.id, 'accorde', demande.commentaire_admin
                    )
                    
                    logger.info(f"Prêt {pret.id} créé pour demande {demande.id}")
                    
                    return Response({
                        'message': 'Prêt accordé avec succès',
                        'demande': LoanApplicationDetailSerializer(demande).data,
                        'pret': LoanSerializer(pret).data
                    })
                
                else:
                    return Response(
                        {'erreur': 'Action non reconnue'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        except Exception as e:
            logger.error(f"Erreur validation admin demande {pk}: {e}")
            return Response(
                {'erreur': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Rapport d'analyse détaillé",
        description="""
        Génère un rapport d'analyse complet pour une demande de prêt.
        
        **Contenu du rapport**:
        - Profil complet du client et historique financier
        - Analyse détaillée du score de fiabilité calculé
        - Évaluation de la capacité de remboursement
        - Recommandations de conditions optimales
        - Analyse des risques et garanties
        - Conformité réglementaire UEMOA/BCEAO
        
        **Calculs automatiques inclus**:
        - Score de fiabilité basé sur épargne et tontines
        - Ratio d'endettement et capacité de remboursement
        - Simulation de tableaux d'amortissement
        - Analyse de sensibilité aux variations de taux
        - Évaluation des garanties proposées
        
        **Sections du rapport**:
        1. Synthèse exécutive avec recommandation
        2. Profil client et historique TontiFlex
        3. Analyse financière et capacité de paiement
        4. Évaluation des risques et mitigation
        5. Recommandations de conditions
        6. Conformité réglementaire et documentation
        
        **Utilisation**:
        - Aide à la décision pour superviseurs et admins
        - Documentation pour dossier de prêt
        - Justification des conditions accordées
        - Traçabilité des analyses effectuées
        """,
        responses={
            200: RapportDemandeSerializer,
            403: OpenApiResponse(description="Non autorisé pour cette demande"),
            404: OpenApiResponse(description="Demande non trouvée"),
            500: OpenApiResponse(description="Erreur génération rapport")
        }
    )
    @action(detail=True, methods=['get'], url_path='rapport-analyse')
    def rapport_analyse(self, request, pk=None):
        """Génère un rapport d'analyse détaillé de la demande."""
        demande = self.get_object()
        
        try:
            rapport = generer_rapport_demande(demande)
            return Response(rapport)
        except Exception as e:
            logger.error(f"Erreur génération rapport demande {pk}: {e}")
            return Response(
                {'erreur': 'Erreur lors de la génération du rapport'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# =============================================================================
# CONDITIONS DE REMBOURSEMENT
# =============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="Liste des conditions de remboursement",
        description="""
        Affiche la liste des conditions de remboursement définies pour les demandes de prêt.
        
        Les conditions de remboursement TontiFlex:
        Définies exclusivement par les Superviseurs SFD après examen
        Incluent montant accordé, taux d'intérêt, durée et clauses particulières
        Personnalisées selon le profil de risque du client
        Conformes aux réglementations UEMOA et politiques SFD
        
        Éléments des conditions:
        Montant accordé (peut être inférieur au montant demandé)
        Taux d'intérêt annuel selon grille SFD et profil client
        Durée de remboursement en mois (3 à 36 mois maximum)
        Type de remboursement (mensuel, bimensuel, saisonnier)
        Garanties requises et modalités de recouvrement
        Clauses particulières (assurance, remboursement anticipé)
        
        Calculs automatiques:
        Mensualité calculée selon tableau d'amortissement
        Coût total du crédit et taux effectif global (TEG)
        Calendrier détaillé des échéances
        Simulations de remboursement anticipé
        """,
        responses={200: LoanTermsSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Créer des conditions de remboursement",
        description="""
        Permet de créer de nouvelles conditions de remboursement pour une demande.
        
        Processus de création:
        Réservé aux Superviseurs SFD pour leurs clients
        Basé sur l'analyse approfondie de la demande
        Respect des grilles de taux et politiques SFD
        Validation automatique de cohérence
        
        Données requises:
        Référence à la demande de prêt concernée
        Montant accordé (dans les limites autorisées)
        Taux d'intérêt conforme à la grille SFD
        Durée adaptée au profil et à l'activité
        Garanties et conditions particulières
        """,
        request=LoanTermsSerializer,
        responses={
            201: LoanTermsSerializer,
            400: OpenApiResponse(description="Conditions invalides ou hors limites"),
            403: OpenApiResponse(description="Non autorisé à définir les conditions")
        }
    ),
    retrieve=extend_schema(
        summary="Détails des conditions de remboursement",
        description="Récupère les informations détaillées des conditions avec simulation d'amortissement."
    ),
    update=extend_schema(
        summary="Modifier les conditions de remboursement",
        description="""
        Met à jour les conditions de remboursement existantes.
        
        Modifications autorisées:
        Superviseur: Peut modifier avant transfert admin
        Admin SFD: Peut ajuster avant validation finale
        Restrictions selon le statut de la demande
        """
    ),
    partial_update=extend_schema(
        summary="Modification partielle des conditions",
        description="Met à jour partiellement les conditions de remboursement."
    ),
    destroy=extend_schema(
        summary="Supprimer les conditions",
        description="Supprime les conditions (uniquement si demande non encore validée)."
    )
)
@extend_schema(tags=["📊 Conditions de Remboursement"])
class LoanTermsViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des conditions de remboursement.
    """
    serializer_class = LoanTermsSerializer
    permission_classes = [CanDefineTerms]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.type_utilisateur == 'superviseur_sfd':
            return LoanTerms.objects.filter(
                demande__client__compte_epargne__agent_validateur__sfd=user.sfd
            )
        elif user.type_utilisateur in ['admin_sfd', 'admin_plateforme']:
            if user.type_utilisateur == 'admin_sfd':
                return LoanTerms.objects.filter(
                    demande__client__compte_epargne__agent_validateur__sfd=user.sfd
                )
            else:
                return LoanTerms.objects.all()
        
        return LoanTerms.objects.none()
    
    @extend_schema(
        summary="Simuler un tableau d'amortissement",
        description="""
        Génère une simulation de tableau d'amortissement pour des conditions données.
        
        **Outil de simulation TontiFlex**:
        - Calcul précis des mensualités selon méthode actuarielle
        - Décomposition capital/intérêts pour chaque échéance
        - Solde restant dû après chaque paiement
        - Coût total du crédit et TEG (Taux Effectif Global)
        
        **Paramètres de simulation**:
        - Montant du prêt (capital initial)
        - Taux d'intérêt annuel (en pourcentage)
        - Durée de remboursement (en mois)
        - Date de première échéance (optionnelle)
        
        **Informations calculées**:
        - Mensualité fixe pour remboursement constant
        - Répartition capital/intérêts par échéance
        - Capital restant dû à chaque période
        - Somme totale remboursée sur la durée
        - Coût total des intérêts
        
        **Cas d'usage**:
        - Aide à la définition des conditions par les superviseurs
        - Présentation au client des modalités de remboursement
        - Validation de la capacité de paiement
        - Comparaison de différents scénarios
        
        **Exemple de calcul**:
        Pour un prêt de 500 000 FCFA à 12% sur 12 mois:
        Mensualité: ~44 424 FCFA
        Total remboursé: ~533 088 FCFA
        Coût crédit: ~33 088 FCFA
        """,
        parameters=[
            OpenApiParameter(
                'montant', 
                OpenApiTypes.NUMBER, 
                location=OpenApiParameter.QUERY,
                description="Montant du prêt en FCFA"
            ),
            OpenApiParameter(
                'taux', 
                OpenApiTypes.NUMBER, 
                location=OpenApiParameter.QUERY,
                description="Taux d'intérêt annuel en pourcentage"
            ),
            OpenApiParameter(
                'duree', 
                OpenApiTypes.INT, 
                location=OpenApiParameter.QUERY,
                description="Durée de remboursement en mois"
            ),
            OpenApiParameter(
                'date_debut', 
                OpenApiTypes.DATE, 
                location=OpenApiParameter.QUERY,
                description="Date de première échéance (optionnel)",
                required=False
            )
        ],
        responses={
            200: CalendrierRemboursementSerializer,
            400: OpenApiResponse(description="Paramètres de simulation invalides")
        },
        examples=[
            OpenApiExample(
                "Simulation prêt commerce",
                description="Simulation pour un prêt commercial typique",
                value={
                    "montant": 500000,
                    "taux": 12,
                    "duree": 12
                }
            ),
            OpenApiExample(
                "Simulation prêt agriculture",
                description="Simulation adaptée aux cycles agricoles",
                value={
                    "montant": 300000,
                    "taux": 10,
                    "duree": 18
                }
            )
        ]
    )
    @action(detail=False, methods=['get'], url_path='simuler-amortissement')
    def simuler_amortissement(self, request):
        """Simule un tableau d'amortissement."""
        try:
            montant = Decimal(request.GET.get('montant', 0))
            taux = Decimal(request.GET.get('taux', 0))
            duree = int(request.GET.get('duree', 0))
            
            if not all([montant > 0, taux >= 0, duree > 0]):
                return Response(
                    {'erreur': 'Paramètres invalides'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Date de première échéance (dans 1 mois)
            date_debut = (timezone.now() + timedelta(days=30)).date()
            
            tableau = calculer_tableau_amortissement(montant, taux, duree, date_debut)
            
            return Response({
                'tableau_amortissement': tableau,
                'resume': {
                    'montant_principal': float(montant),
                    'duree_mois': duree,
                    'taux_annuel': float(taux),
                    'mensualite': float(tableau[0]['mensualite']) if tableau else 0,
                    'total_rembourse': sum(float(e['mensualite']) for e in tableau),
                    'cout_interet': sum(float(e['mensualite']) for e in tableau) - float(montant)
                }
            })
            
        except Exception as e:
            logger.error(f"Erreur simulation amortissement: {e}")
            return Response(
                {'erreur': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# =============================================================================
# PRÊTS ACCORDÉS
# =============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="Liste des prêts accordés",
        description="""
        Affiche la liste des prêts accordés selon les permissions utilisateur.
        
        Cycle de vie d'un prêt TontiFlex:
        1. Création automatique après validation Admin SFD
        2. Statut 'accorde' - Prêt approuvé, en attente de décaissement
        3. Statut 'decaisse' - Fonds remis au client, début remboursement
        4. Statut 'en_remboursement' - Paiements en cours selon calendrier
        5. Statut 'solde' - Prêt intégralement remboursé
        6. Statut 'en_defaut' - Retards importants, procédures de recouvrement
        
        Informations sur les prêts:
        Données complètes du contrat et conditions
        Montant accordé, taux, durée et calendrier
        Historique des décaissements et remboursements
        Solde restant dû et prochaines échéances
        Statut de conformité et alertes de retard
        
        Gestion des risques:
        Suivi automatique des échéances et retards
        Calcul des pénalités selon règlement SFD
        Alertes escaladées selon durée de retard
        Procédures de recouvrement graduées
        """,
        responses={200: LoanSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Créer un prêt (Interne)",
        description="""
        Crée un nouveau prêt (généralement automatique après validation admin).
        
        Processus de création:
        Déclenché automatiquement par validation Admin SFD
        Génération du contrat et du calendrier d'échéances
        Attribution d'un numéro de contrat unique
        Initialisation du suivi de remboursement
        """
    ),
    retrieve=extend_schema(
        summary="Détails d'un prêt",
        description="""
        Récupère les informations détaillées d'un prêt spécifique.
        
        Informations détaillées:
        Contrat complet avec toutes les conditions
        Calendrier d'échéances avec statuts à jour
        Historique des paiements effectués
        Solde restant dû et prochaines échéances
        Calculs des pénalités si retards
        Alertes et actions de recouvrement en cours
        """
    ),
    update=extend_schema(
        summary="Modifier un prêt",
        description="""
        Met à jour les informations d'un prêt existant.
        
        Modifications autorisées:
        Admin SFD: Ajustements exceptionnels des conditions
        Système: Mise à jour automatique des statuts et soldes
        Restructuration: Modification calendrier en cas de difficultés
        """
    ),
    partial_update=extend_schema(
        summary="Modification partielle d'un prêt",
        description="Met à jour partiellement un prêt existant."
    ),
    destroy=extend_schema(
        summary="Supprimer un prêt",
        description="Supprime un prêt (uniquement si aucun décaissement effectué)."
    )
)
@extend_schema(tags=["🏦 Prêts Accordés"])
class LoanViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des prêts accordés.
    """
    serializer_class = LoanSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        if user.type_utilisateur == 'client':
            return Loan.objects.filter(client=user).order_by('-date_creation')
        
        elif user.type_utilisateur in ['agent_sfd', 'superviseur_sfd', 'admin_sfd']:
            return Loan.objects.filter(
                client__compte_epargne__agent_validateur__sfd=user.sfd
            ).order_by('-date_creation')
        
        elif user.type_utilisateur == 'admin_plateforme':
            return Loan.objects.all().order_by('-date_creation')
        
        return Loan.objects.none()
    
    def get_serializer_class(self):
        if self.action in ['retrieve', 'list']:
            return LoanSerializer
        elif self.action == 'decaissement':
            return MarquerDecaisseSerializer
        return self.serializer_class
    
    def get_permissions(self):
        if self.action in ['retrieve', 'list']:
            return [LoanPermission()]
        elif self.action == 'decaissement':
            return [CanMarkDisbursed()]
        return [permissions.IsAuthenticated()]
    
    @extend_schema(
        summary="Marquer un prêt comme décaissé",
        description="""
        Marque un prêt comme décaissé après remise effective des fonds.
        
        **Processus de décaissement TontiFlex**:
        - Vérification de l'identité du bénéficiaire en personne
        - Signature du contrat de prêt définitif
        - Remise des fonds selon mode choisi (espèces/virement/chèque)
        - Activation du calendrier de remboursement
        - Début du suivi des échéances automatique
        
        **Conditions requises**:
        - Prêt en statut 'accorde' uniquement
        - Présence physique du client pour signature
        - Vérification pièce d'identité et documents
        - Fonds SFD disponibles et provisionnés
        
        **Modes de décaissement**:
        - Espèces: Remise directe au guichet SFD
        - Virement: Transfert vers compte bancaire client
        - Chèque: Émission chèque certifié SFD
        - Mobile Money: Transfert direct (si autorisé)
        
        **Effets du décaissement**:
        - Statut prêt → 'decaisse'
        - Déclenchement calendrier de remboursement
        - Notifications automatiques au client
        - Début du suivi des échéances
        - Comptabilisation dans les encours SFD
        
        **Sécurité et traçabilité**:
        - Signature électronique ou scan du contrat
        - Photo de remise des fonds
        - Enregistrement audio/vidéo si montant important
        - Logs complets de l'opération
        """,
        request=MarquerDecaisseSerializer,
        responses={
            200: LoanSerializer,
            400: OpenApiResponse(description="Prêt non décaissable ou données invalides"),
            403: OpenApiResponse(description="Non autorisé à effectuer le décaissement"),
            404: OpenApiResponse(description="Prêt non trouvé")
        },
        examples=[
            OpenApiExample(
                "Décaissement en espèces",
                value={
                    "date_decaissement": "2025-06-26",
                    "mode_decaissement": "especes",
                    "commentaire": "Décaissement effectué au guichet Cotonou Centre, client présent avec CNI",
                    "numero_recu": "DEC2025001234",
                    "agent_decaisseur": "Agent SFD Marie KONE"
                }
            ),
            OpenApiExample(
                "Décaissement par virement",
                value={
                    "date_decaissement": "2025-06-26", 
                    "mode_decaissement": "virement",
                    "commentaire": "Virement vers compte UBA client confirmé",
                    "reference_bancaire": "VIR2025987654",
                    "compte_beneficiaire": "BN123456789"
                }
            )
        ]
    )
    @action(detail=True, methods=['post'], url_path='decaissement')
    def decaissement(self, request, pk=None):
        """Marquer un prêt comme décaissé."""
        pret = self.get_object()
        
        if pret.statut != 'accorde':
            return Response(
                {'erreur': 'Ce prêt ne peut pas être décaissé'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Marquer comme décaissé
                pret.marquer_decaisse(
                    date_decaissement=request.data.get('date_decaissement'),
                    commentaire=request.data.get('commentaire', ''),
                    mode_decaissement=request.data.get('mode_decaissement', 'especes')
                )
                
                logger.info(f"Prêt {pret.id} décaissé par {request.user.id}")
                
                return Response({
                    'message': 'Prêt décaissé avec succès',
                    'pret': LoanDetailSerializer(pret).data
                })
        
        except Exception as e:
            logger.error(f"Erreur décaissement prêt {pk}: {e}")
            return Response(
                {'erreur': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Calendrier de remboursement complet",
        description="""
        Obtient le calendrier de remboursement détaillé d'un prêt.
        
        **Informations du calendrier**:
        - Toutes les échéances prévues avec dates et montants
        - Décomposition capital/intérêts pour chaque paiement
        - Statut de chaque échéance (prévu/payé/en retard)
        - Solde restant dû après chaque paiement
        - Calcul des pénalités pour retards
        
        **Statuts des échéances**:
        - 'prevu': Échéance future non encore due
        - 'en_cours': Échéance due dans les 5 jours
        - 'en_retard': Échéance non payée après date limite
        - 'paye': Échéance intégralement réglée
        - 'paye_partiel': Paiement partiel effectué
        
        **Calculs automatiques**:
        - Solde restant dû actualisé
        - Pénalités de retard selon règlement SFD
        - Intérêts de retard calculés quotidiennement
        - Projection des échéances futures
        
        **Gestion des retards**:
        - Calcul automatique des pénalités
        - Rééchelonnement des soldes
        - Alertes escaladées selon durée
        - Procédures de recouvrement graduées
        
        **Résumé inclus**:
        - Nombre total d'échéances
        - Échéances payées vs restantes
        - Montant total remboursé vs prévu
        - Retards éventuels et pénalités
        """,
        responses={
            200: CalendrierRemboursementSerializer,
            403: OpenApiResponse(description="Non autorisé à consulter ce calendrier"),
            404: OpenApiResponse(description="Prêt non trouvé")
        }
    )
    @action(detail=True, methods=['get'], url_path='calendrier-remboursement')
    def calendrier_remboursement(self, request, pk=None):
        """Obtient le calendrier de remboursement complet."""
        pret = self.get_object()
        echeances = pret.echeances.all().order_by('numero_echeance')
        
        return Response({
            'pret': LoanSerializer(pret).data,
            'echeances': RepaymentScheduleSerializer(echeances, many=True).data,
            'resume': {
                'total_echeances': echeances.count(),
                'echeances_payees': echeances.filter(statut='paye').count(),
                'echeances_en_retard': echeances.filter(statut='en_retard').count(),
                'montant_total_prevu': sum(e.montant_total for e in echeances),
                'montant_paye': sum(e.montant_paye for e in echeances),
                'montant_restant': sum(e.montant_restant for e in echeances)
            }
        })


# =============================================================================
# ÉCHÉANCES DE REMBOURSEMENT
# =============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="Liste des échéances de remboursement",
        description="""
        Affiche la liste des échéances de remboursement selon les permissions.
        
        Gestion des échéances TontiFlex:
        Générées automatiquement lors du décaissement du prêt
        Calendrier fixe selon conditions définies (mensuel/bimensuel)
        Mise à jour automatique des statuts et pénalités
        Intégration avec système Mobile Money pour remboursements
        
        Statuts d'échéance:
        prevu: Échéance future, pas encore due
        en_cours: Échéance due dans les 5 prochains jours
        en_retard: Échéance non payée après date limite + période de grâce
        paye: Échéance intégralement réglée et confirmée
        paye_partiel: Paiement partiel reçu, solde restant
        
        Calculs automatiques:
        Décomposition capital/intérêts selon tableau d'amortissement
        Pénalités de retard calculées quotidiennement
        Intérêts de retard composés selon règlement SFD
        Mise à jour temps réel des soldes restants
        
        Alertes et notifications:
        Rappels automatiques J-5, J-1 et J+1
        Escalade vers superviseur/admin selon durée de retard
        SMS et emails de rappel personnalisés
        Notifications Mobile Money pour faciliter paiement
        """,
        responses={200: RepaymentScheduleSerializer(many=True)}
    ),
    retrieve=extend_schema(
        summary="Détails d'une échéance",
        description="""
        Récupère les informations détaillées d'une échéance spécifique.
        
        Informations détaillées:
        Montant total, décomposition capital/intérêts
        Date d'échéance et statut actuel
        Historique des paiements partiels si applicable
        Calcul des pénalités et intérêts de retard
        Options de paiement Mobile Money disponibles
        """
    )
)
@extend_schema(tags=["📅 Échéances de Remboursement"])
class RepaymentScheduleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour consulter les échéances de remboursement.
    """
    serializer_class = RepaymentScheduleSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        if user.type_utilisateur == 'client':
            return RepaymentSchedule.objects.filter(
                pret__client=user
            ).order_by('date_echeance')
        
        elif user.type_utilisateur in ['agent_sfd', 'superviseur_sfd', 'admin_sfd']:
            return RepaymentSchedule.objects.filter(
                pret__client__compte_epargne__agent_validateur__sfd=user.sfd
            ).order_by('date_echeance')
        
        elif user.type_utilisateur == 'admin_plateforme':
            return RepaymentSchedule.objects.all().order_by('date_echeance')
        
        return RepaymentSchedule.objects.none()
    
    @extend_schema(
        summary="Échéances à venir",
        description="""
        Récupère les échéances à venir dans une période donnée.
        
        **Fonctionnalité de suivi proactif**:
        - Identification des échéances approchant de leur date limite
        - Priorisation par montant et client à risque
        - Préparation des actions de relance préventive
        - Planification des liquidités SFD nécessaires
        
        **Critères de sélection**:
        - Échéances dans la période spécifiée (défaut: 30 jours)
        - Statuts 'prevu' et 'en_retard' uniquement
        - Tri par date d'échéance croissante
        - Filtrage par SFD selon permissions utilisateur
        
        **Utilisation par rôle**:
        - Client: Ses propres échéances à venir pour planification
        - Agent SFD: Échéances clients pour suivi et relance
        - Superviseur: Vision consolidée pour pilotage
        - Admin: Planification globale des encaissements
        
        **Informations enrichies**:
        - Profil de risque du client
        - Historique de ponctualité
        - Moyens de contact préférés
        - Options de paiement Mobile Money
        """,
        parameters=[
            OpenApiParameter(
                'jours', 
                OpenApiTypes.INT, 
                location=OpenApiParameter.QUERY, 
                default=30,
                description="Nombre de jours dans le futur à considérer"
            )
        ],
        responses={200: RepaymentScheduleSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], url_path='a-venir')
    def a_venir(self, request):
        """Obtient les échéances à venir."""
        jours = int(request.GET.get('jours', 30))
        date_limite = timezone.now().date() + timedelta(days=jours)
        
        echeances = self.get_queryset().filter(
            date_echeance__lte=date_limite,
            statut__in=['prevu', 'en_retard']
        )
        
        return Response(RepaymentScheduleSerializer(echeances, many=True).data)
    
    @extend_schema(
        summary="Échéances en retard",
        description="""
        Récupère toutes les échéances en retard nécessitant une action de recouvrement.
        
        **Gestion du recouvrement TontiFlex**:
        - Identification automatique des retards dès J+1
        - Classification par gravité selon durée de retard
        - Calcul automatique des pénalités cumulées
        - Déclenchement des procédures de recouvrement graduées
        
        **Niveaux de retard**:
        - 1-7 jours: Rappel amiable, contact téléphonique
        - 8-15 jours: Relance formelle, visite client si local
        - 16-30 jours: Mise en demeure, implication superviseur
        - 31+ jours: Procédure de recouvrement, saisie garanties
        
        **Actions automatiques**:
        - Calcul quotidien des pénalités selon barème SFD
        - Notifications escaladées aux équipes de recouvrement
        - Blocage de nouveaux prêts pour client en retard
        - Mise à jour du score de fiabilité client
        
        **Informations de recouvrement**:
        - Durée exacte du retard en jours
        - Montant total dû (capital + intérêts + pénalités)
        - Historique des actions de recouvrement
        - Coordonnées client et personnes de contact
        - Garanties mobilisables si disponibles
        """,
        responses={200: RepaymentScheduleSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], url_path='en-retard')
    def en_retard(self, request):
        """Obtient les échéances en retard."""
        echeances = self.get_queryset().filter(
            statut='en_retard',
            date_echeance__lt=timezone.now().date()
        )
        
        return Response(RepaymentScheduleSerializer(echeances, many=True).data)


# =============================================================================
# PAIEMENTS
# =============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="Liste des paiements de remboursement",
        description="""
        Affiche la liste des paiements effectués pour les remboursements de prêts.
        
        Système de paiement TontiFlex:
        Remboursements exclusivement via Mobile Money (MTN/Moov)
        Traitement temps réel avec confirmation automatique
        Réconciliation automatique avec les échéances
        Gestion des paiements partiels et reports
        
        Types de paiement:
        remboursement_normal: Paiement d'échéance selon calendrier
        remboursement_anticipe: Paiement avant date d'échéance
        remboursement_retard: Paiement après date limite avec pénalités
        remboursement_partiel: Paiement inférieur au montant dû
        solde_final: Dernier paiement soldant intégralement le prêt
        
        Statuts Mobile Money:
        en_attente: Transaction initiée, en cours de traitement
        confirme: Paiement validé par opérateur Mobile Money
        echec: Transaction échouée (solde insuffisant, erreur technique)
        timeout: Délai de confirmation dépassé
        
        Traçabilité complète:
        Référence unique pour chaque transaction
        Horodatage précis des opérations
        Logs de toutes les tentatives de paiement
        Historique des confirmations et rejets
        """,
        responses={200: PaymentSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Effectuer un paiement de remboursement",
        description="""
        Permet d'effectuer un paiement de remboursement via Mobile Money.
        
        Processus de remboursement:
        1. Client initie paiement depuis son interface ou USSD
        2. Vérification de l'échéance et du montant
        3. Initiation transaction Mobile Money
        4. Confirmation par l'opérateur (MTN/Moov)
        5. Mise à jour automatique de l'échéance
        6. Notifications de confirmation au client et à la SFD
        
        Contrôles de sécurité:
        Authentification Mobile Money requise (PIN)
        Vérification du solde client suffisant
        Validation de l'échéance et du montant
        Prévention de la double déduction
        
        Gestion des cas particuliers:
        Paiements partiels autorisés avec report du solde
        Remboursements anticipés sans pénalité
        Paiements multiples pour une même échéance
        Annulation et remboursement en cas d'erreur
        """,
        request=PaymentSerializer,
        responses={
            201: PaymentSerializer,
            400: OpenApiResponse(description="Données de paiement invalides"),
            402: OpenApiResponse(description="Solde Mobile Money insuffisant"),
            404: OpenApiResponse(description="Échéance non trouvée"),
            503: OpenApiResponse(description="Service Mobile Money indisponible")
        },
        examples=[
            OpenApiExample(
                "Paiement échéance normale",
                value={
                    "echeance": 123,
                    "montant": 44424,
                    "numero_telephone": "+22370123456",  # MIGRATION : KKiaPay simplifié
                    # operateur et pin_mobile_money supprimés - KKiaPay gère automatiquement
                    "description": "Remboursement échéance mensuelle juin 2025"
                }
            ),
            OpenApiExample(
                "Paiement partiel",
                value={
                    "echeance": 124,
                    "montant": 20000,
                    "numero_telephone": "+22369876543",
                    "description": "Paiement partiel - solde à reporter"
                }
            )
        ]
    ),
    retrieve=extend_schema(
        summary="Détails d'un paiement",
        description="""
        Récupère les informations détaillées d'un paiement spécifique.
        
        Informations détaillées:
        Données complètes de la transaction Mobile Money
        Statut de confirmation et références externes
        Échéance associée et impact sur le solde
        Historique des tentatives si multiple
        Informations de réconciliation comptable
        """
    ),
    update=extend_schema(
        summary="Modifier un paiement",
        description="""
        Met à jour un paiement existant (correction d'erreurs administratives).
        
        Modifications autorisées:
        Agents SFD: Correction statut pour réconciliation
        Admin: Ajustements exceptionnels avec justification
        Système: Mise à jour automatique des confirmations
        """
    ),
    partial_update=extend_schema(
        summary="Modification partielle d'un paiement",
        description="Met à jour partiellement un paiement existant."
    ),
    destroy=extend_schema(
        summary="Supprimer un paiement",
        description="Supprime un paiement (uniquement si échec confirmé et aucun impact)."
    )
)
@extend_schema(tags=["💳 Paiements de Remboursement"])
class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des paiements de remboursement.
    """
    serializer_class = PaymentSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        if user.type_utilisateur == 'client':
            return Payment.objects.filter(
                echeance__pret__client=user
            ).order_by('-date_creation')
        
        elif user.type_utilisateur in ['agent_sfd', 'superviseur_sfd', 'admin_sfd']:
            return Payment.objects.filter(
                echeance__pret__client__compte_epargne__agent_validateur__sfd=user.sfd
            ).order_by('-date_creation')
        
        elif user.type_utilisateur == 'admin_plateforme':
            return Payment.objects.all().order_by('-date_creation')
        
        return Payment.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PaymentSerializer
        return self.serializer_class
    
    def get_permissions(self):
        if self.action == 'create':
            return [CanMakeRepayment()]
        return [permissions.IsAuthenticated()]
    
    def perform_create(self, serializer):
        """Créer un nouveau paiement."""
        try:
            echeance_id = self.request.data.get('echeance')
            montant = Decimal(str(self.request.data.get('montant', 0)))
            
            echeance = get_object_or_404(RepaymentSchedule, id=echeance_id)
            
            # Vérifier que le client peut payer cette échéance
            if self.request.user.type_utilisateur == 'client' and echeance.pret.client != self.request.user:
                raise ValidationError("Vous ne pouvez pas payer cette échéance.")
            
            # Vérifier que l'échéance n'est pas déjà payée
            if echeance.statut == 'paye':
                raise ValidationError("Cette échéance est déjà payée.")
            
            # Créer le paiement
            paiement = serializer.save(
                echeance=echeance,
                montant=montant,
                numero_telephone=self.request.data.get('numero_telephone'),
                statut_kkiapay='pending'
            )
            
            # Initier le paiement KKiaPay
            from .tasks import traiter_remboursement_kkiapay
            traiter_remboursement_kkiapay(paiement.id)
            
            logger.info(f"Paiement {paiement.id} créé pour échéance {echeance.id}")
            
        except Exception as e:
            logger.error(f"Erreur création paiement: {e}")
            raise ValidationError(str(e))
    
    @extend_schema(
        summary="Confirmer un paiement manuellement",
        description="""
        Permet aux agents SFD de confirmer manuellement un paiement.
        
        **Cas d'usage de confirmation manuelle**:
        - Réconciliation après problème technique Mobile Money
        - Confirmation de paiements cash exceptionnels au guichet
        - Correction d'erreurs de traitement automatique
        - Validation de virements bancaires directs
        
        **Processus de confirmation**:
        1. Vérification de l'identité de l'agent confirmateur
        2. Validation de la référence externe du paiement
        3. Contrôle de cohérence avec registres SFD
        4. Mise à jour du statut et de l'échéance associée
        5. Génération des notifications de confirmation
        
        **Sécurité et contrôles**:
        - Seuls agents SFD et superviseurs autorisés
        - Obligation de référence externe justificative
        - Logs complets de l'action avec traçabilité
        - Notification automatique au superviseur
        
        **Effets de la confirmation**:
        - Statut paiement → 'confirme'
        - Mise à jour de l'échéance correspondante
        - Recalcul du solde restant dû du prêt
        - Notifications client et équipes SFD
        
        **Traçabilité**:
        - Identification de l'agent confirmateur
        - Horodatage précis de la confirmation
        - Référence du justificatif externe
        - Commentaires explicatifs obligatoires
        """,
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'reference_externe': {
                        'type': 'string',
                        'description': 'Référence du paiement dans système externe'
                    },
                    'commentaire': {
                        'type': 'string', 
                        'description': 'Justification de la confirmation manuelle'
                    },
                    'mode_paiement': {
                        'type': 'string',
                        'enum': ['kkiapay_auto', 'especes_guichet', 'virement_bancaire', 'cheque'],
                        'description': 'Mode de paiement confirmé'
                    }
                },
                'required': ['reference_externe', 'commentaire']
            }
        },
        responses={
            200: PaymentSerializer,
            400: OpenApiResponse(description="Paiement déjà confirmé ou données invalides"),
            403: OpenApiResponse(description="Non autorisé à confirmer les paiements"),
            404: OpenApiResponse(description="Paiement non trouvé")
        },
        examples=[
            OpenApiExample(
                "Confirmation après problème technique",
                value={
                    "reference_externe": "MTN_REF_789456123",
                    "commentaire": "Confirmation manuelle après timeout technique MTN - paiement vérifié sur relevé opérateur",
                    "mode_paiement": "kkiapay_auto"
                }
            ),
            OpenApiExample(
                "Paiement espèces exceptionnel",
                value={
                    "reference_externe": "CASH_REC_2025_001234",
                    "commentaire": "Paiement en espèces autorisé exceptionnellement - client en zone sans couverture Mobile Money",
                    "mode_paiement": "especes_guichet"
                }
            )
        ]
    )
    @action(detail=True, methods=['post'], url_path='confirmer')
    def confirmer(self, request, pk=None):
        """Confirmer un paiement manuellement (pour les agents)."""
        paiement = self.get_object()
        
        # Seuls les agents/admins peuvent confirmer manuellement
        if request.user.type_utilisateur not in ['agent_sfd', 'superviseur_sfd', 'admin_sfd', 'admin_plateforme']:
            return Response(
                {'erreur': 'Non autorisé'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if paiement.statut_kkiapay == 'success':
            return Response(
                {'erreur': 'Ce paiement est déjà confirmé'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Confirmer le paiement
                paiement.statut_kkiapay = 'success'
                paiement.date_confirmation = timezone.now()
                paiement.reference_externe = request.data.get('reference_externe', '')
                paiement.confirme_par = request.user
                paiement.save()
                
                # Déclencher la confirmation (met à jour l'échéance)
                paiement.confirmer_paiement()
                
                return Response({
                    'message': 'Paiement confirmé avec succès',
                    'paiement': PaymentSerializer(paiement).data
                })
        
        except Exception as e:
            logger.error(f"Erreur confirmation paiement {pk}: {e}")
            return Response(
                {'erreur': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# =============================================================================
# RAPPORTS ET STATISTIQUES
# =============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="Endpoints de rapports et statistiques",
        description="""
        ViewSet fournissant les endpoints pour générer des rapports et statistiques sur les prêts.
        
        Fonctionnalités disponibles:
        - Statistiques consolidées par période
        - Tableau de bord temps réel par rôle
        - Rapports d'analyse de performance
        - Indicateurs de risque et recouvrement
        - Exportation de données pour audit
        """
    )
)
@extend_schema(tags=["📊 Rapports et Statistiques"])
class LoanReportViewSet(viewsets.ViewSet):
    """
    ViewSet pour les rapports et statistiques des prêts.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Statistiques générales des prêts",
        description="""
        Génère des statistiques consolidées sur l'activité de prêts.
        
        **Métriques calculées**:
        - Volume et nombre de demandes sur la période
        - Taux d'approbation et de rejet par étape du workflow
        - Montants décaissés et en cours de remboursement
        - Performance de recouvrement et taux de défaut
        - Durée moyenne de traitement des demandes
        
        **Indicateurs de performance**:
        - Portefeuille à risque (PAR) à 30, 60 et 90+ jours
        - Taux de récupération et provisions nécessaires
        - Rendement sur actifs de crédit (ROA)
        - Coût du risque et rentabilité par segment
        
        **Segmentation des données**:
        - Par type de prêt (commerce, agriculture, consommation)
        - Par montant (micro, petit, moyen crédit)
        - Par profil client (score de fiabilité)
        - Par agent/superviseur traitant
        
        **Évolution temporelle**:
        - Comparaison avec périodes précédentes
        - Tendances mensuelles et saisonnières
        - Projections basées sur pipeline actuel
        - Alertes sur déviations significatives
        
        **Filtrage par SFD**:
        Agents/Superviseurs/Admins SFD: Données de leur SFD uniquement
        Admin Plateforme: Vue consolidée toutes SFD
        """,
        parameters=[
            OpenApiParameter(
                'periode_mois', 
                OpenApiTypes.INT, 
                location=OpenApiParameter.QUERY, 
                default=12,
                description="Nombre de mois à inclure dans l'analyse (défaut: 12)"
            ),
            OpenApiParameter(
                'type_pret',
                OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filtrer par type de prêt spécifique",
                required=False
            ),
            OpenApiParameter(
                'montant_min',
                OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
                description="Montant minimum des prêts à inclure",
                required=False
            ),
            OpenApiParameter(
                'montant_max',
                OpenApiTypes.NUMBER,
                location=OpenApiParameter.QUERY,
                description="Montant maximum des prêts à inclure", 
                required=False
            )
        ],
        responses={
            200: OpenApiResponse(description="Statistiques des prêts récupérées"),
            403: OpenApiResponse(description="Non autorisé à consulter les statistiques"),
            500: OpenApiResponse(description="Erreur calcul des statistiques")
        }
    )
    @action(detail=False, methods=['get'], url_path='statistiques')
    def statistiques(self, request):
        """Obtient les statistiques des prêts."""
        periode_mois = int(request.GET.get('periode_mois', 12))
        
        # Filtrer par SFD si applicable
        sfd = None
        if request.user.type_utilisateur in ['agent_sfd', 'superviseur_sfd', 'admin_sfd']:
            sfd = request.user.sfd
        
        try:
            stats = calculer_statistiques_prets(sfd=sfd, periode_mois=periode_mois)
            return Response(stats)
        except Exception as e:
            logger.error(f"Erreur calcul statistiques: {e}")
            return Response(
                {'erreur': 'Erreur lors du calcul des statistiques'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @extend_schema(
        summary="Tableau de bord des prêts",
        description="""
        Interface de pilotage temps réel de l'activité de prêts avec KPI visuels.
        
        **Widgets de monitoring en temps réel**:
        - Demandes en attente par étape (Agent → Superviseur → Admin SFD)  
        - Prêts décaissés aujourd'hui/cette semaine/ce mois
        - Remboursements attendus vs reçus (jour/semaine/mois)
        - Alertes prêts en retard par niveau de gravité
        
        **Indicateurs de performance**:
        - Volume portefeuille actif et évolution
        - Taux de défaut et provisions nécessaires
        - Délai moyen traitement demandes par étape
        - Productivité agents (demandes traitées/jour)
        
        **Alertes et actions prioritaires**:
        - Prêts en retard nécessitant un suivi immédiat
        - Demandes dépassant les délais standards
        - Dépassements de limite par agent/superviseur
        - Anomalies détectées dans les patterns
        
        **Navigation rapide**:
        - Liens directs vers demandes en attente d'action
        - Accès rapide aux dossiers problématiques
        - Shortcut vers outils de reporting
        - Actions en un clic (approbations simples)
        
        **Personnalisation par rôle**:
        - Agent: Focus sur ses demandes et clients
        - Superviseur: Vue équipe et validation
        - Admin SFD: Pilotage global SFD
        - Admin Plateforme: Monitoring multi-SFD
        
        **Rafraîchissement automatique**:
        Données mises à jour en temps réel via WebSocket
        Cache intelligent pour performance optimale
        """,
        parameters=[
            OpenApiParameter(
                'niveau_detail',
                OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                default='standard',
                enum=['minimal', 'standard', 'detaille'],
                description="Niveau de détail du tableau de bord (minimal/standard/detaille)"
            ),
            OpenApiParameter(
                'periode_analyse',
                OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                default='7d',
                enum=['1d', '7d', '30d', '90d'],
                description="Période d'analyse pour tendances (1d/7d/30d/90d)"
            ),
            OpenApiParameter(
                'widgets_actifs',
                OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Liste widgets à afficher (séparés par virgule)",
                required=False
            )
        ],
        responses={
            200: OpenApiResponse(description="Données du tableau de bord récupérées"),
            403: OpenApiResponse(description="Non autorisé à accéder au tableau de bord"),
            500: OpenApiResponse(description="Erreur génération tableau de bord")
        }
    )
    @action(detail=False, methods=['get'])
    def tableau_bord(self, request):
        """Tableau de bord avec indicateurs clés."""
        try:
            user = request.user
            
            # Construire les filtres selon le type d'utilisateur
            if user.type_utilisateur == 'client':
                # Dashboard client
                demandes = LoanApplication.objects.filter(client=user)
                prets = Loan.objects.filter(client=user)
                
                dashboard = {
                    'type': 'client',
                    'demandes': {
                        'total': demandes.count(),
                        'en_cours': demandes.exclude(statut__in=['accorde', 'rejete']).count(),
                        'accordees': demandes.filter(statut='accorde').count(),
                        'rejetees': demandes.filter(statut='rejete').count()
                    },
                    'prets': {
                        'total': prets.count(),
                        'en_cours': prets.exclude(statut__in=['solde', 'en_defaut']).count(),
                        'soldes': prets.filter(statut='solde').count()
                    }
                }
                
                # Prochaines échéances
                prochaines_echeances = RepaymentSchedule.objects.filter(
                    pret__client=user,
                    statut__in=['prevu', 'en_retard'],
                    date_echeance__lte=timezone.now().date() + timedelta(days=30)
                ).order_by('date_echeance')[:5]
                
                dashboard['prochaines_echeances'] = RepaymentScheduleSerializer(
                    prochaines_echeances, many=True
                ).data
                
            else:
                # Dashboard agent/admin
                # Filtrer par SFD
                if user.type_utilisateur in ['agent_sfd', 'superviseur_sfd', 'admin_sfd']:
                    demandes = LoanApplication.objects.filter(
                        client__compte_epargne__agent_validateur__sfd=user.sfd
                    )
                    prets = Loan.objects.filter(
                        client__compte_epargne__agent_validateur__sfd=user.sfd
                    )
                else:
                    demandes = LoanApplication.objects.all()
                    prets = Loan.objects.all()
                
                from django.db import models
                
                dashboard = {
                    'type': 'admin',
                    'demandes_en_attente': {
                        'soumises': demandes.filter(statut='soumis').count(),
                        'transferees': demandes.filter(statut='transfere_admin').count(),
                        'total': demandes.exclude(statut__in=['accorde', 'rejete']).count()
                    },
                    'prets_a_decaisser': prets.filter(statut='accorde').count(),
                    'echeances_en_retard': RepaymentSchedule.objects.filter(
                        pret__in=prets,
                        statut='en_retard'
                    ).count(),
                    'montant_en_cours': float(
                        prets.filter(statut__in=['decaisse', 'en_remboursement'])
                        .aggregate(total=models.Sum('montant_accorde'))['total'] or 0
                    )
                }
            
            return Response(dashboard)
            
        except Exception as e:
            logger.error(f"Erreur tableau de bord: {e}")
            return Response(
                {'erreur': 'Erreur lors de la génération du tableau de bord'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def get_client_from_request(request):
    """Récupère le client depuis la requête."""
    if hasattr(request.user, 'client'):
        return request.user.client
    return request.user if request.user.type_utilisateur == 'client' else None
