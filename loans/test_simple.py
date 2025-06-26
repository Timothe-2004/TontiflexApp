"""
Test simple pour vérifier que le module loans fonctionne de base.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import SFD, Client, AgentSFD
from savings.models import SavingsAccount
from loans.models import LoanApplication
from decimal import Decimal

User = get_user_model()


class SimpleLoansTest(TestCase):
    """Test simple du module loans."""
    
    def setUp(self):
        """Configuration initiale minimale."""
        # Créer une SFD
        self.sfd = SFD.objects.create(
            id="SFD_TEST",
            nom="SFD Test Simple",
            adresse="Adresse test",
            telephone="22890000000",
            email="test@sfd.com",
            numeroMobileMoney="22890000000"
        )
        
        # Créer un User Django pour le client
        self.django_user = User.objects.create_user(
            username="testclient",
            email="client@test.com",
            password="testpass123"
        )
        
        # Créer un Client TontiFlex
        self.client_user = Client.objects.create(
            user=self.django_user,
            nom="Doe",
            prenom="John",
            telephone="22890123456",
            email="client@test.com",
            adresse="Adresse client test",
            profession="Commerçant",
            motDePasse="testpass123"
        )
        
        # Créer un Agent SFD
        self.agent_django_user = User.objects.create_user(
            username="testagent",
            email="agent@test.com", 
            password="testpass123"
        )
        
        self.agent = AgentSFD.objects.create(
            user=self.agent_django_user,
            nom="Agent",
            prenom="Test",
            telephone="22890123457",
            email="agent@test.com",
            adresse="Adresse agent test",
            profession="Agent SFD",
            motDePasse="testpass123",
            sfd=self.sfd
        )
    
    def test_creation_sfd(self):
        """Test que la SFD peut être créée."""
        self.assertEqual(self.sfd.nom, "SFD Test Simple")
        self.assertEqual(self.sfd.id, "SFD_TEST")
    
    def test_creation_utilisateurs(self):
        """Test que les utilisateurs peuvent être créés."""
        self.assertEqual(self.django_user.username, "testclient")
        self.assertEqual(self.client_user.nom, "Doe")
        self.assertEqual(self.agent.nom, "Agent")
    
    def test_creation_compte_epargne(self):
        """Test la création d'un compte épargne."""
        compte = SavingsAccount.objects.create(
            client=self.client_user,
            agent_validateur=self.agent,
            statut="actif"
        )
        self.assertEqual(compte.client, self.client_user)
        self.assertEqual(compte.statut, "actif")
    
    def test_creation_demande_pret_basic(self):
        """Test la création d'une demande de prêt basique."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        # D'abord créer le compte épargne
        compte = SavingsAccount.objects.create(
            client=self.client_user,
            agent_validateur=self.agent,
            statut="actif"
        )
        
        # Créer un fichier PDF fictif pour les tests
        pdf_content = b'%PDF-1.4 test file content'
        pdf_file = SimpleUploadedFile(
            "test_document.pdf",
            pdf_content,
            content_type="application/pdf"
        )
        
        # Puis créer la demande de prêt avec les bons noms de champs
        demande = LoanApplication.objects.create(
            client=self.client_user,
            nom="Doe",
            prenom="John",
            date_naissance="1990-01-01",
            adresse_domicile="Adresse test",
            situation_familiale="celibataire",
            telephone="22890123456",
            email="john@test.com",
            situation_professionnelle="Commerçant indépendant",
            justificatif_identite="CNI",
            revenu_mensuel=Decimal('100000'),
            charges_mensuelles=Decimal('30000'),
            montant_souhaite=Decimal('500000'),
            duree_pret=12,
            type_pret="consommation",
            objet_pret="Achat de marchandises",
            type_garantie="aucune",
            signature_collecte_donnees=True,
            document_complet=pdf_file,
            statut="soumis"
        )
        
        self.assertEqual(demande.client, self.client_user)
        self.assertEqual(demande.montant_souhaite, Decimal('500000'))
        self.assertEqual(demande.statut, "soumis")


class LoansViewsTest(TestCase):
    """Test simple des vues du module loans."""
    
    def test_import_views(self):
        """Test que les vues peuvent être importées."""
        from loans.views import (
            LoanApplicationViewSet, LoanTermsViewSet, LoanViewSet,
            RepaymentScheduleViewSet, PaymentViewSet, LoanReportViewSet
        )
        # Si on arrive ici, les imports fonctionnent
        self.assertTrue(True)
    
    def test_import_models(self):
        """Test que les modèles peuvent être importés."""
        from loans.models import (
            LoanApplication, LoanTerms, Loan, 
            RepaymentSchedule, Payment
        )
        # Si on arrive ici, les imports fonctionnent
        self.assertTrue(True)
    
    def test_import_serializers(self):
        """Test que les serializers peuvent être importés."""
        from loans.serializers import (
            LoanApplicationSerializer, LoanTermsSerializer, 
            LoanSerializer, RepaymentScheduleSerializer, PaymentSerializer
        )
        # Si on arrive ici, les imports fonctionnent
        self.assertTrue(True)
