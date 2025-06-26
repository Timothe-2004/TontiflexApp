"""
TESTS POUR LE MODULE PRÊTS - TONTIFLEX

Tests complets pour:
1. Modèles et règles métier
2. Workflow Superviseur → Admin obligatoire
3. Calculs financiers et échéances
4. Permissions et sécurité
5. API REST et endpoints
6. Intégration Mobile Money
7. Notifications et tâches asynchrones

Couverture complète du module prêts
"""

import json
import logging
from decimal import Decimal
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from accounts.models import SFD
from savings.models import SavingsAccount
from .models import LoanApplication, LoanTerms, Loan, RepaymentSchedule, Payment
from .utils import (
    calculer_mensualite, calculer_tableau_amortissement,
    calculer_score_fiabilite_client, analyser_capacite_remboursement
)

User = get_user_model()


# =============================================================================
# TESTS DES MODÈLES
# =============================================================================

class LoanApplicationModelTest(TestCase):
    """Tests pour le modèle LoanApplication."""
    
    def setUp(self):
        """Configuration initiale des tests."""
        # Créer une SFD
        self.sfd = SFD.objects.create(
            id="SFD001",
            nom="SFD Test",
            adresse="Adresse test",
            telephone="22890000000",
            email="test@sfd.com",
            numeroMobileMoney="22890000000"
        )
        
        # Créer un client
        self.client_user = User.objects.create_user(
            username="client1",
            nom="Doe",
            prenom="John",
            telephone="22890123456",
            email="john@test.com",
            type_utilisateur="client",
            password="testpass123"
        )
        
        # Créer un agent SFD
        self.agent = User.objects.create_user(
     username="user2",
            username="agent1",
            nom="Agent",
            prenom="Test",
            telephone="22890123457",
            email="agent@test.com",
            type_utilisateur="agent_sfd",
            sfd=self.sfd,
            password="testpass123"
 )
        
        # Créer un superviseur SFD
        self.superviseur = User.objects.create_user(
     username="user3",
            username="superviseur1",
            nom="Superviseur",
            prenom="Test",
            telephone="22890123458",
            email="superviseur@test.com",
            type_utilisateur="superviseur_sfd",
            sfd=self.sfd,
            password="testpass123"
 )
        
        # Créer un admin SFD
        self.admin_sfd = User.objects.create_user(
     username="user4",
            username="admin1",
            nom="Admin",
            prenom="SFD",
            telephone="22890123459",
            email="admin@test.com",
            type_utilisateur="admin_sfd",
            sfd=self.sfd,
            password="testpass123"
 )
        
        # Créer un compte épargne pour le client
        self.compte_epargne = SavingsAccount.objects.create(
            client=self.client_user,
            agent_validateur=self.agent,
            statut="actif",
            date_activation=timezone.now() - timedelta(days=100)  # Plus de 3 mois
        )
    
    def test_creation_demande_valide(self):
        """Test création d'une demande de prêt valide."""
        demande = LoanApplication.objects.create(
            client=self.client_user,
            montant_souhaite=Decimal('500000'),
            duree_pret=12,
            type_pret="consommation",
            objet_pret="Achat matériel",
            revenus_mensuel=Decimal('150000'),
            charges_mensuelles=Decimal('80000'),
            situation_familiale="marie",
            situation_professionnelle="salarie"
        )
        
        self.assertEqual(demande.statut, 'soumis')
        self.assertEqual(demande.ratio_endettement, Decimal('53.33'))
        self.assertTrue(demande.est_eligible)
    
    def test_eligibilite_compte_epargne_recent(self):
        """Test que l'éligibilité échoue si le compte épargne est trop récent."""
        # Modifier la date d'activation (moins de 3 mois)
        self.compte_epargne.date_activation = timezone.now() - timedelta(days=50)
        self.compte_epargne.save()
        
        demande = LoanApplication(
            client=self.client_user,
            montant_souhaite=Decimal('500000'),
            duree_pret=12,
            type_pret="consommation",
            objet_pret="Test"
        )
        
        self.assertFalse(demande.est_eligible)
    
    def test_workflow_superviseur_admin(self):
        """Test du workflow obligatoire Superviseur → Admin."""
        demande = LoanApplication.objects.create(
            client=self.client_user,
            montant_souhaite=Decimal('500000'),
            duree_pret=12,
            type_pret="consommation",
            objet_pret="Test",
            revenus_mensuel=Decimal('150000'),
            charges_mensuelles=Decimal('80000')
        )
        
        # Traitement par le superviseur
        conditions = LoanTerms.objects.create(
            demande=demande,
            montant_accorde=Decimal('450000'),
            taux_interet_annuel=Decimal('15.0'),
            duree_mois=12,
            definies_par=self.superviseur
        )
        
        demande.statut = 'transfere_admin'
        demande.superviseur_traitant = self.superviseur
        demande.save()
        
        self.assertEqual(demande.statut, 'transfere_admin')
        self.assertEqual(demande.conditions_remboursement, conditions)
    
    def test_creation_pret_apres_validation_admin(self):
        """Test création automatique du prêt après validation admin."""
        demande = LoanApplication.objects.create(
            client=self.client_user,
            montant_souhaite=Decimal('500000'),
            duree_pret=12,
            type_pret="consommation",
            objet_pret="Test",
            revenus_mensuel=Decimal('150000'),
            charges_mensuelles=Decimal('80000'),
            statut='transfere_admin'
        )
        
        conditions = LoanTerms.objects.create(
            demande=demande,
            montant_accorde=Decimal('450000'),
            taux_interet_annuel=Decimal('15.0'),
            duree_mois=12,
            definies_par=self.superviseur
        )
        
        # Validation par l'admin
        pret = Loan.objects.create(
            demande=demande,
            client=self.client_user,
            montant_accorde=conditions.montant_accorde,
            taux_interet_annuel=conditions.taux_interet_annuel,
            duree_mois=conditions.duree_mois,
            admin_validateur=self.admin_sfd
        )
        
        self.assertEqual(pret.statut, 'accorde')
        self.assertEqual(pret.montant_accorde, Decimal('450000'))
        self.assertTrue(pret.reference.startswith('LOAN_'))


class LoanModelTest(TestCase):
    """Tests pour le modèle Loan."""
    
    def setUp(self):
        """Configuration initiale."""
        self.sfd = SFD.objects.create(
            id="SFD002",
            nom="SFD Test",
            adresse="Adresse test",
            telephone="22890000000",
            email="test@sfd.com",
            numeroMobileMoney="22890000000"
        )
        
        self.client_user = User.objects.create_user(
     username="user5",
            username="client2",
            nom="Doe",
            prenom="John",
            telephone="22890123456",
            email="john@test.com",
            type_utilisateur="client",
            password="testpass123"
 )
        
        self.admin_sfd = User.objects.create_user(
     username="user6",
            nom="Admin",
            prenom="SFD",
            telephone="22890123459",
            email="admin@test.com",
            type_utilisateur="admin_sfd",
            sfd=self.sfd,
            password="testpass123"
 )
        
        self.demande = LoanApplication.objects.create(
            client=self.client_user,
            montant_souhaite=Decimal('500000'),
            duree_pret=12,
            type_pret="consommation",
            objet_pret="Test"
        )
    
    def test_generation_echeances_apres_decaissement(self):
        """Test génération automatique des échéances après décaissement."""
        pret = Loan.objects.create(
            demande=self.demande,
            client=self.client_user,
            montant_accorde=Decimal('500000'),
            taux_interet_annuel=Decimal('12.0'),
            duree_mois=12,
            admin_validateur=self.admin_sfd
        )
        
        # Marquer comme décaissé
        pret.marquer_decaisse(
            date_decaissement=date.today(),
            commentaire="Test décaissement"
        )
        
        self.assertEqual(pret.statut, 'decaisse')
        self.assertEqual(pret.echeances.count(), 12)
        
        # Vérifier la première échéance
        premiere_echeance = pret.echeances.first()
        self.assertEqual(premiere_echeance.numero_echeance, 1)
        self.assertTrue(premiere_echeance.montant_principal > 0)
        self.assertTrue(premiere_echeance.montant_interet > 0)
    
    def test_calcul_progression_remboursement(self):
        """Test calcul de la progression du remboursement."""
        pret = Loan.objects.create(
            demande=self.demande,
            client=self.client_user,
            montant_accorde=Decimal('500000'),
            taux_interet_annuel=Decimal('12.0'),
            duree_mois=12,
            admin_validateur=self.admin_sfd
        )
        
        pret.marquer_decaisse(date_decaissement=date.today())
        
        # Initialement, rien n'est remboursé
        self.assertEqual(pret.montant_rembourse, Decimal('0'))
        self.assertEqual(pret.progression_remboursement, Decimal('0'))
        
        # Simuler un paiement d'échéance
        premiere_echeance = pret.echeances.first()
        premiere_echeance.montant_paye = premiere_echeance.montant_total
        premiere_echeance.statut = 'paye'
        premiere_echeance.save()
        
        # Rafraîchir et vérifier
        pret.refresh_from_db()
        self.assertTrue(pret.montant_rembourse > 0)
        self.assertTrue(pret.progression_remboursement > 0)


# =============================================================================
# TESTS DES UTILITAIRES
# =============================================================================

class CalculsFinanciersTest(TestCase):
    """Tests pour les calculs financiers."""
    
    def test_calcul_mensualite(self):
        """Test calcul de mensualité."""
        # Prêt de 100 000 à 12% sur 12 mois
        mensualite = calculer_mensualite(
            Decimal('100000'),
            Decimal('12.0'),
            12
        )
        
        # Vérifier que la mensualité est cohérente
        self.assertGreater(mensualite, Decimal('8000'))
        self.assertLess(mensualite, Decimal('10000'))
    
    def test_calcul_mensualite_taux_zero(self):
        """Test calcul mensualité avec taux zéro."""
        mensualite = calculer_mensualite(
            Decimal('120000'),
            Decimal('0.0'),
            12
        )
        
        # Doit être exactement 10 000 (120 000 / 12)
        self.assertEqual(mensualite, Decimal('10000.00'))
    
    def test_tableau_amortissement(self):
        """Test génération du tableau d'amortissement."""
        tableau = calculer_tableau_amortissement(
            Decimal('100000'),
            Decimal('12.0'),
            12,
            date(2024, 2, 1)
        )
        
        self.assertEqual(len(tableau), 12)
        
        # Vérifier la première échéance
        premiere = tableau[0]
        self.assertEqual(premiere['numero'], 1)
        self.assertEqual(premiere['date_echeance'], date(2024, 2, 1))
        self.assertGreater(premiere['interet'], Decimal('0'))
        self.assertGreater(premiere['capital'], Decimal('0'))
        
        # Vérifier que le solde diminue
        self.assertGreater(premiere['solde_restant'], tableau[1]['solde_restant'])
        
        # Vérifier que le solde final est zéro
        self.assertEqual(tableau[-1]['solde_restant'], Decimal('0.00'))
    
    def test_score_fiabilite_client(self):
        """Test calcul du score de fiabilité."""
        # Créer un client avec compte épargne
        sfd = SFD.objects.create(
            id="SFD003",
            nom="SFD Test",
            adresse="Test",
            telephone="22890000000",
            email="test@sfd.com",
            numeroMobileMoney="22890000000"
        )
        
        client = User.objects.create_user(
     username="user7",
            nom="Test",
            prenom="Client",
            telephone="22890123456",
            email="client@test.com",
            type_utilisateur="client",
            password="testpass123"
 )
        
        agent = User.objects.create_user(
     username="user8",
            nom="Agent",
            prenom="Test",
            telephone="22890123457",
            email="agent@test.com",
            type_utilisateur="agent_sfd",
            sfd=sfd,
            password="testpass123"
 )
        
        # Créer un compte épargne ancien
        SavingsAccount.objects.create(
            client=client,
            agent_validateur=agent,
            statut="actif",
            date_activation=timezone.now() - timedelta(days=200)
        )
        
        score_info = calculer_score_fiabilite_client(client)
        
        self.assertIn('score', score_info)
        self.assertIn('details', score_info)
        self.assertIn('evaluation', score_info)
        self.assertGreaterEqual(score_info['score'], 0)
        self.assertLessEqual(score_info['score'], 100)
    
    def test_analyse_capacite_remboursement(self):
        """Test analyse de capacité de remboursement."""
        analyse = analyser_capacite_remboursement(
            Decimal('200000'),  # revenus
            Decimal('100000'),  # charges
            Decimal('50000')    # mensualité prêt
        )
        
        self.assertIn('reste_a_vivre_actuel', analyse)
        self.assertIn('nouveau_ratio_endettement', analyse)
        self.assertIn('analyse_favorable', analyse)
        self.assertEqual(analyse['reste_a_vivre_actuel'], 100000)
        self.assertEqual(analyse['nouveau_ratio_endettement'], 75.0)


# =============================================================================
# TESTS DES API REST
# =============================================================================

class LoanApplicationAPITest(APITestCase):
    """Tests pour l'API des demandes de prêt."""
    
    def setUp(self):
        """Configuration initiale."""
        self.sfd = SFD.objects.create(
            id="SFD004",
            nom="SFD Test",
            adresse="Test",
            telephone="22890000000",
            email="test@sfd.com",
            numeroMobileMoney="22890000000"
        )
        
        self.client_user = User.objects.create_user(
     username="user9",
            nom="Client",
            prenom="Test",
            telephone="22890123456",
            email="client@test.com",
            type_utilisateur="client",
            password="testpass123"
 )
        
        self.superviseur = User.objects.create_user(
     username="user10",
            nom="Superviseur",
            prenom="Test",
            telephone="22890123458",
            email="superviseur@test.com",
            type_utilisateur="superviseur_sfd",
            sfd=self.sfd,
            password="testpass123"
 )
        
        self.admin_sfd = User.objects.create_user(
     username="user11",
            nom="Admin",
            prenom="SFD",
            telephone="22890123459",
            email="admin@test.com",
            type_utilisateur="admin_sfd",
            sfd=self.sfd,
            password="testpass123"
 )
        
        # Créer un compte épargne pour le client
        agent = User.objects.create_user(
     username="user12",
            nom="Agent",
            prenom="Test",
            telephone="22890123457",
            email="agent@test.com",
            type_utilisateur="agent_sfd",
            sfd=self.sfd,
            password="testpass123"
 )
        
        SavingsAccount.objects.create(
            client=self.client_user,
            agent_validateur=agent,
            statut="actif",
            date_activation=timezone.now() - timedelta(days=100)
        )
        
        self.client_api = APIClient()
    
    def test_creation_demande_client(self):
        """Test création d'une demande par un client."""
        self.client_api.force_authenticate(user=self.client_user)
        
        data = {
            'montant_souhaite': 500000,
            'duree_pret': 12,
            'type_pret': 'consommation',
            'objet_pret': 'Achat matériel',
            'revenus_mensuel': 150000,
            'charges_mensuelles': 80000,
            'situation_familiale': 'marie',
            'situation_professionnelle': 'salarie'
        }
        
        response = self.client_api.post('/loans/applications/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Vérifier que la demande a été créée
        demande = LoanApplication.objects.get(id=response.data['id'])
        self.assertEqual(demande.client, self.client_user)
        self.assertEqual(demande.statut, 'soumis')
    
    def test_traitement_demande_superviseur(self):
        """Test traitement d'une demande par un superviseur."""
        # Créer une demande
        demande = LoanApplication.objects.create(
            client=self.client_user,
            montant_souhaite=Decimal('500000'),
            duree_pret=12,
            type_pret='consommation',
            objet_pret='Test',
            revenus_mensuel=Decimal('150000'),
            charges_mensuelles=Decimal('80000')
        )
        
        self.client_api.force_authenticate(user=self.superviseur)
        
        data = {
            'action': 'approuver',
            'montant_accorde': 450000,
            'taux_interet': 15.0,
            'duree_mois': 12,
            'commentaire': 'Dossier approuvé'
        }
        
        response = self.client_api.post(
            f'/loans/applications/{demande.id}/process_application/',
            data
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Vérifier que la demande a été transférée à l'admin
        demande.refresh_from_db()
        self.assertEqual(demande.statut, 'transfere_admin')
        self.assertTrue(hasattr(demande, 'conditions_remboursement'))
    
    def test_validation_finale_admin(self):
        """Test validation finale par un admin SFD."""
        # Créer une demande avec conditions
        demande = LoanApplication.objects.create(
            client=self.client_user,
            montant_souhaite=Decimal('500000'),
            duree_pret=12,
            type_pret='consommation',
            objet_pret='Test',
            statut='transfere_admin'
        )
        
        LoanTerms.objects.create(
            demande=demande,
            montant_accorde=Decimal('450000'),
            taux_interet_annuel=Decimal('15.0'),
            duree_mois=12,
            definies_par=self.superviseur
        )
        
        self.client_api.force_authenticate(user=self.admin_sfd)
        
        data = {
            'action': 'valider',
            'commentaire': 'Prêt accordé'
        }
        
        response = self.client_api.post(
            f'/loans/applications/{demande.id}/admin_decision/',
            data
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Vérifier qu'un prêt a été créé
        demande.refresh_from_db()
        self.assertEqual(demande.statut, 'accorde')
        self.assertTrue(Loan.objects.filter(demande=demande).exists())
    
    def test_permissions_acces_demandes(self):
        """Test des permissions d'accès aux demandes."""
        # Créer une demande
        demande = LoanApplication.objects.create(
            client=self.client_user,
            montant_souhaite=Decimal('500000'),
            duree_pret=12,
            type_pret='consommation',
            objet_pret='Test'
        )
        
        # Test accès client
        self.client_api.force_authenticate(user=self.client_user)
        response = self.client_api.get('/loans/applications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        # Test accès superviseur
        self.client_api.force_authenticate(user=self.superviseur)
        response = self.client_api.get('/loans/applications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test accès sans authentification
        self.client_api.force_authenticate(user=None)
        response = self.client_api.get('/loans/applications/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# =============================================================================
# TESTS DES TÂCHES ASYNCHRONES
# =============================================================================

class TasksTest(TestCase):
    """Tests pour les tâches asynchrones."""
    
    def setUp(self):
        """Configuration initiale."""
        self.sfd = SFD.objects.create(
            id="SFD005",
            nom="SFD Test",
            adresse="Test",
            telephone="22890000000",
            email="test@sfd.com",
            numeroMobileMoney="22890000000"
        )
        
        self.client_user = User.objects.create_user(
     username="user13",
            nom="Client",
            prenom="Test",
            telephone="22890123456",
            email="client@test.com",
            type_utilisateur="client",
            password="testpass123"
 )
    
    @patch('loans.tasks.send_mail')
    def test_notification_demande_soumise(self, mock_send_mail):
        """Test notification de demande soumise."""
        from .tasks import envoyer_notification_demande_soumise
        
        demande = LoanApplication.objects.create(
            client=self.client_user,
            montant_souhaite=Decimal('500000'),
            duree_pret=12,
            type_pret='consommation',
            objet_pret='Test'
        )
        
        # Exécuter la tâche
        envoyer_notification_demande_soumise(demande.id)
        
        # Vérifier que l'email a été envoyé
        self.assertTrue(mock_send_mail.called)
    
    @patch('loans.tasks.calculer_penalites_retard')
    def test_calcul_penalites_quotidiennes(self, mock_calcul_penalites):
        """Test calcul quotidien des pénalités."""
        from .tasks import calculer_penalites_quotidiennes
        
        # Créer un prêt avec échéances en retard
        pret = Loan.objects.create(
            client=self.client_user,
            montant_accorde=Decimal('500000'),
            taux_interet_annuel=Decimal('12.0'),
            duree_mois=12
        )
        
        # Créer une échéance en retard
        RepaymentSchedule.objects.create(
            pret=pret,
            numero_echeance=1,
            date_echeance=timezone.now().date() - timedelta(days=5),
            montant_principal=Decimal('40000'),
            montant_interet=Decimal('5000'),
            statut='en_retard'
        )
        
        mock_calcul_penalites.return_value = Decimal('1000')
        
        # Exécuter la tâche
        result = calculer_penalites_quotidiennes()
        
        # Vérifier que le calcul a été effectué
        self.assertGreaterEqual(result, 0)


# =============================================================================
# TESTS D'INTÉGRATION
# =============================================================================

class WorkflowIntegrationTest(TransactionTestCase):
    """Tests d'intégration du workflow complet."""
    
    def setUp(self):
        """Configuration complète."""
        self.sfd = SFD.objects.create(
            id="SFD006",
            nom="SFD Test",
            adresse="Test",
            telephone="22890000000",
            email="test@sfd.com",
            numeroMobileMoney="22890000000"
        )
        
        self.client_user = User.objects.create_user(
     username="user14",
            nom="Client",
            prenom="Test",
            telephone="22890123456",
            email="client@test.com",
            type_utilisateur="client",
            password="testpass123"
 )
        
        self.agent = User.objects.create_user(
     username="user15",
            nom="Agent",
            prenom="Test",
            telephone="22890123457",
            email="agent@test.com",
            type_utilisateur="agent_sfd",
            sfd=self.sfd,
            password="testpass123"
 )
        
        self.superviseur = User.objects.create_user(
     username="user16",
            nom="Superviseur",
            prenom="Test",
            telephone="22890123458",
            email="superviseur@test.com",
            type_utilisateur="superviseur_sfd",
            sfd=self.sfd,
            password="testpass123"
 )
        
        self.admin_sfd = User.objects.create_user(
     username="user17",
            nom="Admin",
            prenom="SFD",
            telephone="22890123459",
            email="admin@test.com",
            type_utilisateur="admin_sfd",
            sfd=self.sfd,
            password="testpass123"
 )
        
        # Créer un compte épargne
        SavingsAccount.objects.create(
            client=self.client_user,
            agent_validateur=self.agent,
            statut="actif",
            date_activation=timezone.now() - timedelta(days=100)
        )
    
    def test_workflow_complet_pret(self):
        """Test du workflow complet d'un prêt."""
        # 1. Création de la demande par le client
        demande = LoanApplication.objects.create(
            client=self.client_user,
            montant_souhaite=Decimal('500000'),
            duree_pret=12,
            type_pret='consommation',
            objet_pret='Achat matériel professionnel',
            revenus_mensuel=Decimal('200000'),
            charges_mensuelles=Decimal('100000'),
            situation_familiale='marie',
            situation_professionnelle='salarie'
        )
        
        self.assertEqual(demande.statut, 'soumis')
        
        # 2. Traitement par le superviseur
        conditions = LoanTerms.objects.create(
            demande=demande,
            montant_accorde=Decimal('450000'),
            taux_interet_annuel=Decimal('15.0'),
            duree_mois=12,
            definies_par=self.superviseur
        )
        
        demande.statut = 'transfere_admin'
        demande.superviseur_traitant = self.superviseur
        demande.date_traitement_superviseur = timezone.now()
        demande.save()
        
        self.assertEqual(demande.statut, 'transfere_admin')
        
        # 3. Validation par l'admin SFD
        pret = Loan.objects.create(
            demande=demande,
            client=self.client_user,
            montant_accorde=conditions.montant_accorde,
            taux_interet_annuel=conditions.taux_interet_annuel,
            duree_mois=conditions.duree_mois,
            admin_validateur=self.admin_sfd
        )
        
        demande.statut = 'accorde'
        demande.admin_validateur = self.admin_sfd
        demande.date_traitement_admin = timezone.now()
        demande.save()
        
        self.assertEqual(pret.statut, 'accorde')
        
        # 4. Décaissement
        pret.marquer_decaisse(
            date_decaissement=date.today(),
            commentaire="Décaissement en agence"
        )
        
        self.assertEqual(pret.statut, 'decaisse')
        self.assertEqual(pret.echeances.count(), 12)
        
        # 5. Simulation d'un paiement
        premiere_echeance = pret.echeances.first()
        
        paiement = Payment.objects.create(
            echeance=premiere_echeance,
            montant=premiere_echeance.montant_total,
            numero_telephone="22890123456",
            statut_mobile_money='confirme'
        )
        
        # Confirmer le paiement
        paiement.confirmer_paiement()
        
        premiere_echeance.refresh_from_db()
        self.assertEqual(premiere_echeance.statut, 'paye')
        
        pret.refresh_from_db()
        self.assertEqual(pret.statut, 'en_remboursement')
        self.assertGreater(pret.montant_rembourse, Decimal('0'))


if __name__ == '__main__':
    import django
    django.setup()
    
    from django.test.runner import DiscoverRunner
    test_runner = DiscoverRunner(verbosity=2)
    failures = test_runner.run_tests(['loans'])
    
    if failures:
        exit(1)
