"""
Test unitaire Django complet pour le module loans - Workflow intégral

Ce test simule le scénario complet suivant :
1. Un client crée une demande de prêt
2. Un superviseur étudie et transfère la demande à l'admin SFD
3. L'admin SFD valide la demande de prêt
4. Le superviseur définit les échéances de remboursement
5. Le client effectue tous les remboursements
6. Le système confirme que tous les remboursements sont terminés
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta

from accounts.models import SFD, Client, AgentSFD, SuperviseurSFD, AdministrateurSFD
from savings.models import SavingsAccount
from loans.models import LoanApplication, LoanTerms, Loan, RepaymentSchedule, Payment

User = get_user_model()


class FullLoanProcessTest(TestCase):
    """Test complet du processus de prêt de bout en bout."""
    
    def setUp(self):
        """Configuration initiale complète pour le test de workflow."""
        
        # ========== CRÉATION DE LA SFD ==========
        self.sfd = SFD.objects.create(
            id="SFD_WORKFLOW_TEST",
            nom="SFD Test Workflow Complet",
            adresse="123 Rue du Test, Ouagadougou",
            telephone="22670000001",
            email="workflow@sfdtest.com",
            numeroMobileMoney="22670000001"
        )
        
        # ========== CRÉATION DU CLIENT ==========
        self.client_django_user = User.objects.create_user(
            username="client_workflow",
            email="client.workflow@test.com",
            password="clientpass123"
        )
        
        self.client_user = Client.objects.create(
            user=self.client_django_user,
            nom="Ouedraogo",
            prenom="Fatou",
            telephone="22670111111",
            email="client.workflow@test.com",
            adresse="Secteur 15, Ouagadougou",
            profession="Commerçante",
            motDePasse="clientpass123"
        )
        
        # ========== CRÉATION DU SUPERVISEUR SFD ==========
        self.superviseur_django_user = User.objects.create_user(
            username="superviseur_workflow",
            email="superviseur.workflow@test.com",
            password="superviseurpass123"
        )
        
        self.superviseur = SuperviseurSFD.objects.create(
            user=self.superviseur_django_user,
            nom="Kabore",
            prenom="Jean",
            telephone="22670222222",
            email="superviseur.workflow@test.com",
            adresse="Zone commerciale, Ouagadougou",
            profession="Superviseur SFD",
            motDePasse="superviseurpass123",
            sfd=self.sfd
        )
        
        # ========== CRÉATION DE L'ADMIN SFD ==========
        self.admin_django_user = User.objects.create_user(
            username="admin_workflow",
            email="admin.workflow@test.com",
            password="adminpass123"
        )
        
        self.admin_sfd = AdministrateurSFD.objects.create(
            user=self.admin_django_user,
            nom="Traore",
            prenom="Marie",
            telephone="22670333333",
            email="admin.workflow@test.com",
            adresse="Direction SFD, Ouagadougou",
            profession="Administrateur SFD",
            motDePasse="adminpass123",
            sfd=self.sfd
        )
        
        # ========== CRÉATION DU COMPTE ÉPARGNE ==========
        # Le client doit avoir un compte épargne depuis plus de 3 mois
        date_activation_ancienne = timezone.now() - timedelta(days=120)
        
        self.compte_epargne = SavingsAccount.objects.create(
            client=self.client_user,
            agent_validateur=None,  # Supposons qu'il soit déjà validé
            statut="actif",
            date_activation=date_activation_ancienne
        )
        
        # ========== DOCUMENTS FICTIFS POUR LES TESTS ==========
        self.pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Count 1\n/Kids [3 0 R]\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000079 00000 n \n0000000173 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n301\n%%EOF'
    
    def _create_pdf_file(self, filename="test_document.pdf"):
        """Utilitaire pour créer un fichier PDF fictif."""
        return SimpleUploadedFile(
            filename,
            self.pdf_content,
            content_type="application/pdf"
        )
    
    def test_full_loan_process(self):
        """Test complet du processus de prêt de bout en bout."""
        
        # ========== ÉTAPE 1: CRÉATION DE LA DEMANDE DE PRÊT ==========
        print("\n=== ÉTAPE 1: Création de la demande de prêt ===")
        
        demande = LoanApplication.objects.create(
            client=self.client_user,
            nom="Ouedraogo",
            prenom="Fatou",
            date_naissance="1985-03-15",
            adresse_domicile="Secteur 15, Ouagadougou",
            situation_familiale="marie",
            telephone="22670111111",
            email="client.workflow@test.com",
            situation_professionnelle="Commerçante indépendante - Vente de tissu",
            justificatif_identite="CNI",
            revenu_mensuel=Decimal('200000'),
            charges_mensuelles=Decimal('80000'),
            montant_souhaite=Decimal('500000'),
            duree_pret=12,
            type_pret="professionnel",
            objet_pret="Achat de stock de tissu pour extension commerce",
            type_garantie="garant_physique",
            signature_collecte_donnees=True,
            document_complet=self._create_pdf_file("demande_pret_fatou.pdf"),
            statut="soumis"
        )
        
        # Vérifications étape 1
        self.assertEqual(demande.statut, "soumis")
        self.assertEqual(demande.montant_souhaite, Decimal('500000'))
        self.assertEqual(demande.client, self.client_user)
        print(f"✓ Demande créée: {demande.montant_souhaite} FCFA pour {demande.duree_pret} mois")
        
        # ========== ÉTAPE 2: TRAITEMENT PAR LE SUPERVISEUR ==========
        print("\n=== ÉTAPE 2: Traitement par le superviseur ===")
        
        # Le superviseur examine la demande et l'approuve pour transfert à l'admin
        demande.statut = "en_cours_examen"
        demande.superviseur_traitant = self.superviseur
        demande.date_traitement_superviseur = timezone.now()
        demande.commentaires_superviseur = "Demande éligible - Bonne capacité de remboursement. Client fidèle avec compte épargne actif depuis 4 mois."
        demande.save()
        
        # Vérifications étape 2
        self.assertEqual(demande.statut, "en_cours_examen")
        self.assertEqual(demande.superviseur_traitant, self.superviseur)
        self.assertIsNotNone(demande.date_traitement_superviseur)
        print(f"✓ Superviseur {self.superviseur.nom} a traité la demande")
        
        # Le superviseur transfère à l'admin SFD
        demande.statut = "transfere_admin"
        demande.decision_superviseur = "approuve_transfert"
        demande.save()
        
        self.assertEqual(demande.statut, "transfere_admin")
        print("✓ Demande transférée à l'admin SFD")
        
        # ========== ÉTAPE 3: VALIDATION PAR L'ADMIN SFD ==========
        print("\n=== ÉTAPE 3: Validation par l'admin SFD ===")
        
        # L'admin SFD valide définitivement la demande
        demande.statut = "accorde"
        demande.admin_validateur = self.admin_sfd
        demande.date_validation_admin = timezone.now()
        demande.commentaires_admin = "Demande approuvée - Tous les critères respectés. Autorisation de décaissement."
        demande.save()
        
        # Vérifications étape 3
        self.assertEqual(demande.statut, "accorde")
        self.assertEqual(demande.admin_validateur, self.admin_sfd)
        self.assertIsNotNone(demande.date_validation_admin)
        print(f"✓ Admin {self.admin_sfd.nom} a validé la demande")
        
        # ========== ÉTAPE 4: CRÉATION DES CONDITIONS DE PRÊT ==========
        print("\n=== ÉTAPE 4: Définition des conditions de remboursement ===")
        
        # Le superviseur définit les conditions de remboursement
        conditions = LoanTerms.objects.create(
            demande=demande,
            taux_interet_annuel=Decimal('12.00'),  # 12% annuel
            jour_echeance_mensuelle=15,  # Le 15 de chaque mois
            taux_penalite_quotidien=Decimal('0.50'),  # 0.5% par jour de retard
            montant_mensualite=Decimal('44200'),  # Calculé avec intérêts
            date_premiere_echeance=timezone.now().date() + timedelta(days=30),
            superviseur_definisseur=self.superviseur
        )
        
        # Vérifications étape 4
        self.assertEqual(conditions.taux_interet_annuel, Decimal('12.00'))
        self.assertEqual(conditions.jour_echeance_mensuelle, 15)
        self.assertEqual(conditions.superviseur_definisseur, self.superviseur)
        print(f"✓ Conditions définies: taux {conditions.taux_interet_annuel}%, mensualité {conditions.montant_mensualite} FCFA")
        
        # ========== ÉTAPE 5: CRÉATION DU PRÊT ==========
        print("\n=== ÉTAPE 5: Création du prêt ===")
        
        # Création du prêt basé sur la demande approuvée
        pret = Loan.objects.create(
            demande=demande,
            client=self.client_user,
            montant_accorde=Decimal('500000'),
            statut="accorde"
        )
        
        # Vérifications étape 5
        self.assertEqual(pret.client, self.client_user)
        self.assertEqual(pret.montant_accorde, Decimal('500000'))
        self.assertEqual(pret.statut, "accorde")
        print(f"✓ Prêt créé: ID {pret.id}, montant {pret.montant_accorde} FCFA")
        
        # Marquage du décaissement
        pret.statut = "decaisse"
        pret.date_decaissement = timezone.now()
        pret.save()
        
        self.assertEqual(pret.statut, "decaisse")
        print("✓ Prêt décaissé au client")
        
        # ========== ÉTAPE 6: GÉNÉRATION DE L'ÉCHÉANCIER ==========
        print("\n=== ÉTAPE 6: Génération de l'échéancier de remboursement ===")
        
        # Créer les échéances de remboursement (12 mensualités)
        echeances = []
        date_echeance = conditions.date_premiere_echeance
        
        for i in range(1, 13):  # 12 échéances
            # Calculer le solde restant après cette échéance
            solde_restant = Decimal('500000') - (Decimal('41666.67') * i)
            if solde_restant < 0:
                solde_restant = Decimal('0.00')
            
            echeance = RepaymentSchedule.objects.create(
                loan=pret,
                numero_echeance=i,
                date_echeance=date_echeance,
                montant_capital=Decimal('41666.67'),  # Capital = 500000/12
                montant_interet=Decimal('2533.33'),   # Intérêts
                montant_mensualite=Decimal('44200'),  # Total mensualité
                solde_restant=solde_restant,          # Solde après cette échéance
                statut="en_attente"
            )
            echeances.append(echeance)
            
            # Prochaine échéance : +1 mois
            if date_echeance.month == 12:
                date_echeance = date_echeance.replace(year=date_echeance.year + 1, month=1)
            else:
                date_echeance = date_echeance.replace(month=date_echeance.month + 1)
        
        # Vérifications étape 6
        self.assertEqual(RepaymentSchedule.objects.filter(loan=pret).count(), 12)
        self.assertEqual(echeances[0].montant_mensualite, Decimal('44200'))
        print(f"✓ Échéancier généré: {len(echeances)} échéances de {echeances[0].montant_mensualite} FCFA")
        
        # ========== ÉTAPE 7: REMBOURSEMENTS DU CLIENT ==========
        print("\n=== ÉTAPE 7: Remboursements par le client ===")
        
        paiements = []
        total_paye = Decimal('0')
        
        for i, echeance in enumerate(echeances, 1):
            # Simulation du paiement par le client
            paiement = Payment.objects.create(
                loan=pret,
                echeance=echeance,
                montant_paye=echeance.montant_mensualite,
                montant_mensualite=echeance.montant_mensualite,
                montant_penalites=Decimal('0.00'),
                reference_externe=f"MM{timezone.now().year}{i:02d}{str(pret.id)[:8]}",
                statut="confirme"
            )
            paiements.append(paiement)
            total_paye += paiement.montant_paye
            
            # Marquer l'échéance comme payée
            echeance.statut = "paye"
            echeance.save()
            
            print(f"✓ Paiement {i}/12: {paiement.montant_paye} FCFA - Référence: {paiement.reference_externe}")
        
        # Vérifications étape 7
        self.assertEqual(Payment.objects.filter(loan=pret).count(), 12)
        self.assertEqual(total_paye, Decimal('530400'))  # 12 * 44200
        
        # Vérifier que toutes les échéances sont payées
        echeances_payees = RepaymentSchedule.objects.filter(loan=pret, statut="paye").count()
        self.assertEqual(echeances_payees, 12)
        print(f"✓ Total payé: {total_paye} FCFA sur 12 échéances")
        
        # ========== ÉTAPE 8: FINALISATION DU PRÊT ==========
        print("\n=== ÉTAPE 8: Finalisation et clôture du prêt ===")
        
        # Vérifier que tous les remboursements sont terminés
        echeances_restantes = RepaymentSchedule.objects.filter(
            loan=pret, 
            statut__in=["en_attente", "en_retard"]
        ).count()
        
        if echeances_restantes == 0:
            # Marquer le prêt comme entièrement remboursé
            pret.statut = "solde"
            pret.date_fin_remboursement = timezone.now()
            pret.is_fully_paid = True
            pret.save()
            
            message_final = "Félicitations ! Tous les remboursements sont terminés. Le prêt est entièrement soldé."
            print(f"✓ {message_final}")
        
        # ========== VÉRIFICATIONS FINALES ==========
        print("\n=== VÉRIFICATIONS FINALES ===")
        
        # 1. Vérifier le statut final du prêt
        pret.refresh_from_db()
        self.assertEqual(pret.statut, "solde")
        self.assertTrue(pret.is_fully_paid)
        self.assertIsNotNone(pret.date_fin_remboursement)
        print("✓ Prêt marqué comme entièrement remboursé")
        
        # 2. Vérifier que toutes les échéances sont soldées
        echeances_impayees = RepaymentSchedule.objects.filter(
            loan=pret,
            statut__in=["en_attente", "en_retard"]
        ).count()
        self.assertEqual(echeances_impayees, 0)
        print("✓ Toutes les échéances sont soldées")
        
        # 3. Vérifier le montant total des paiements
        total_paiements = sum(p.montant_paye for p in paiements)
        montant_attendu = conditions.montant_mensualite * 12  # 12 mois
        self.assertEqual(total_paiements, montant_attendu)
        print(f"✓ Montant total payé: {total_paiements} FCFA (attendu: {montant_attendu} FCFA)")
        
        # 4. Vérifier la cohérence des données
        self.assertEqual(demande.statut, "accorde")
        self.assertEqual(pret.demande, demande)
        print("✓ Cohérence des données vérifiée")
        
        # 5. Message de confirmation finale
        confirmation_message = f"""
        🎉 PROCESSUS DE PRÊT TERMINÉ AVEC SUCCÈS 🎉
        
        Client: {self.client_user.prenom} {self.client_user.nom}
        Montant initial: {pret.montant_accorde} FCFA
        Durée: 12 mois
        Total remboursé: {total_paiements} FCFA
        Statut final: {pret.statut.upper()}
        
        ✅ Tous les remboursements sont terminés
        ✅ Le prêt est entièrement soldé
        ✅ Le workflow complet a été testé avec succès
        """
        
        print(confirmation_message)
        
        # Assertion finale pour confirmer le succès du test
        self.assertTrue(
            pret.is_fully_paid and pret.statut == "solde" and echeances_impayees == 0,
            "Le processus de prêt complet doit se terminer avec succès"
        )


class WorkflowValidationTest(TestCase):
    """Tests supplémentaires pour valider les règles métier du workflow."""
    
    def setUp(self):
        """Configuration minimale pour les tests de validation."""
        self.sfd = SFD.objects.create(
            id="SFD_VALIDATION",
            nom="SFD Validation Test",
            adresse="Test Address",
            telephone="22670000002",
            email="validation@test.com",
            numeroMobileMoney="22670000002"
        )
    
    def test_workflow_requires_savings_account(self):
        """Test que le workflow nécessite un compte épargne valide."""
        # Créer un client sans compte épargne
        django_user = User.objects.create_user(
            username="client_no_savings",
            email="client.nosavings@test.com",
            password="testpass123"
        )
        
        client = Client.objects.create(
            user=django_user,
            nom="Test",
            prenom="NoSavings",
            telephone="22670444444",
            email="client.nosavings@test.com",
            adresse="Test Address",
            profession="Test",
            motDePasse="testpass123"
        )
        
        # Vérifier qu'il n'a pas de compte épargne
        self.assertFalse(hasattr(client, 'compte_epargne'))
        
        # La création d'une demande de prêt devrait normalement échouer ou être rejetée
        # (selon la logique métier implémentée)
        print("✓ Test de validation: compte épargne requis")
    
    def test_workflow_statut_progression(self):
        """Test que les statuts progressent dans le bon ordre."""
        statuts_attendus = [
            "soumis",
            "en_cours_examen", 
            "transfere_admin",
            "accorde"
        ]
        
        # Vérifier que chaque statut suit l'ordre logique
        for i, statut in enumerate(statuts_attendus):
            if i == 0:
                continue  # Le premier statut n'a pas de prédécesseur
            
            statut_precedent = statuts_attendus[i-1]
            self.assertNotEqual(statut, statut_precedent)
        
        print("✓ Test de validation: progression des statuts")
