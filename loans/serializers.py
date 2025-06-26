"""
SERIALIZERS DJANGO REST FRAMEWORK POUR LE MODULE PRÊTS - TONTIFLEX

Ce module contient tous les serializers pour:
1. Demandes de prêt (formulaire complet)
2. Conditions de remboursement
3. Prêts accordés
4. Échéances et paiements
5. Actions personnalisées (workflow)

Suit les patterns des modules existants (tontines, savings)
"""

from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from django.core.files.base import ContentFile
import base64

from .models import LoanApplication, LoanTerms, Loan, RepaymentSchedule, Payment


# =============================================================================
# SERIALIZERS PRINCIPAUX
# =============================================================================

class LoanApplicationSerializer(serializers.ModelSerializer):
    """Serializer pour les demandes de prêt"""
    client_nom = serializers.CharField(source='client.nom_complet', read_only=True)
    superviseur_nom = serializers.CharField(source='superviseur_examinateur.nom_complet', read_only=True)
    admin_nom = serializers.CharField(source='admin_validateur.nom_complet', read_only=True)
    prochaine_action = serializers.CharField(read_only=True)
    score_fiabilite_display = serializers.SerializerMethodField()
    ratio_endettement_display = serializers.SerializerMethodField()
    age_demandeur = serializers.SerializerMethodField()
    
    # Champ pour upload de document en base64
    document_complet_base64 = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = LoanApplication
        fields = [
            'id', 'client', 'client_nom', 'superviseur_examinateur', 'superviseur_nom',
            'admin_validateur', 'admin_nom', 'statut', 'date_soumission',
            'date_examen_superviseur', 'date_transfert_admin', 'date_validation_admin',
            'date_decaissement',
            # Informations personnelles
            'nom', 'prenom', 'date_naissance', 'age_demandeur',
            'adresse_domicile', 'adresse_bureau', 'situation_familiale',
            'telephone', 'email', 'situation_professionnelle', 'justificatif_identite',
            # Situation financière
            'revenu_mensuel', 'charges_mensuelles', 'ratio_endettement_display',
            'historique_prets_anterieurs', 'plan_affaires',
            # Détails du prêt
            'montant_souhaite', 'duree_pret', 'type_pret', 'objet_pret',
            # Garanties
            'type_garantie', 'details_garantie', 'signature_caution',
            # Consentements
            'signature_collecte_donnees',
            # Documents
            'document_complet', 'document_complet_base64',
            # Commentaires
            'commentaires_superviseur', 'commentaires_admin', 'raison_rejet',
            'score_fiabilite', 'score_fiabilite_display',
            # Métadonnées
            'date_creation', 'date_modification', 'prochaine_action'
        ]
        extra_kwargs = {
            'client': {'required': True},
            'signature_collecte_donnees': {'required': True},
            'document_complet': {'required': False},  # Peut être fourni en base64
        }
    
    def get_score_fiabilite_display(self, obj):
        """Affichage formaté du score de fiabilité"""
        if obj.score_fiabilite:
            return f"{obj.score_fiabilite}/100"
        return "Non calculé"
    
    def get_ratio_endettement_display(self, obj):
        """Affichage formaté du ratio d'endettement"""
        ratio = obj.ratio_endettement
        if ratio > 0:
            return f"{ratio:.1f}%"
        return "0%"
    
    def get_age_demandeur(self, obj):
        """Calcul de l'âge du demandeur"""
        if obj.date_naissance:
            age = (timezone.now().date() - obj.date_naissance).days / 365.25
            return int(age)
        return None
    
    def validate(self, data):
        """Validation des données de la demande"""
        # Validation consentement obligatoire
        if not data.get('signature_collecte_donnees', False):
            raise serializers.ValidationError({
                'signature_collecte_donnees': 'Le consentement pour la collecte des données est obligatoire'
            })
        
        # Validation cohérence financière
        revenu = data.get('revenu_mensuel')
        charges = data.get('charges_mensuelles')
        if revenu and charges and charges >= revenu:
            raise serializers.ValidationError({
                'charges_mensuelles': 'Les charges ne peuvent pas être supérieures ou égales aux revenus'
            })
        
        # Validation âge minimum
        date_naissance = data.get('date_naissance')
        if date_naissance:
            age = (timezone.now().date() - date_naissance).days / 365.25
            if age < 18:
                raise serializers.ValidationError({
                    'date_naissance': 'Le demandeur doit être majeur (18 ans minimum)'
                })
        
        return data
    
    def create(self, validated_data):
        """Création avec gestion du document base64"""
        document_base64 = validated_data.pop('document_complet_base64', None)
        
        # Créer l'instance
        instance = super().create(validated_data)
        
        # Traiter le document base64 si fourni
        if document_base64:
            try:
                # Décoder le base64
                format, imgstr = document_base64.split(';base64,')
                ext = format.split('/')[-1]
                data = ContentFile(base64.b64decode(imgstr), name=f'loan_doc_{instance.id}.{ext}')
                instance.document_complet = data
                instance.save()
            except Exception as e:
                raise serializers.ValidationError({
                    'document_complet_base64': f'Erreur de traitement du document: {str(e)}'
                })
        
        return instance


class LoanTermsSerializer(serializers.ModelSerializer):
    """Serializer pour les conditions de remboursement"""
    demande_info = serializers.CharField(source='demande.__str__', read_only=True)
    superviseur_nom = serializers.CharField(source='superviseur_definisseur.nom_complet', read_only=True)
    montant_total_pret = serializers.SerializerMethodField()
    cout_total_interet = serializers.SerializerMethodField()
    
    class Meta:
        model = LoanTerms
        fields = [
            'id', 'demande', 'demande_info', 'taux_interet_annuel',
            'jour_echeance_mensuelle', 'taux_penalite_quotidien',
            'montant_mensualite', 'date_premiere_echeance',
            'superviseur_definisseur', 'superviseur_nom',
            'montant_total_pret', 'cout_total_interet',
            'date_creation'
        ]
        extra_kwargs = {
            'montant_mensualite': {'read_only': True},
            'date_premiere_echeance': {'read_only': True},
        }
    
    def get_montant_total_pret(self, obj):
        """Calcule le montant total à rembourser"""
        return obj.montant_mensualite * obj.demande.duree_pret
    
    def get_cout_total_interet(self, obj):
        """Calcule le coût total des intérêts"""
        total_rembourse = obj.montant_mensualite * obj.demande.duree_pret
        return total_rembourse - obj.demande.montant_souhaite
    
    def validate_jour_echeance_mensuelle(self, value):
        """Validation du jour d'échéance"""
        if not 1 <= value <= 31:
            raise serializers.ValidationError("Le jour d'échéance doit être entre 1 et 31")
        return value
    
    def validate_taux_interet_annuel(self, value):
        """Validation du taux d'intérêt"""
        if value < 0 or value > 50:
            raise serializers.ValidationError("Le taux d'intérêt doit être entre 0% et 50%")
        return value


class LoanSerializer(serializers.ModelSerializer):
    """Serializer pour les prêts accordés"""
    client_nom = serializers.CharField(source='client.nom_complet', read_only=True)
    demande_info = serializers.CharField(source='demande.__str__', read_only=True)
    admin_decaisseur_nom = serializers.CharField(source='admin_decaisseur.nom_complet', read_only=True)
    montant_total_rembourse = serializers.ReadOnlyField()
    solde_restant_du = serializers.ReadOnlyField()
    est_en_retard = serializers.ReadOnlyField()
    progression_remboursement = serializers.SerializerMethodField()
    
    class Meta:
        model = Loan
        fields = [
            'id', 'demande', 'demande_info', 'client', 'client_nom',
            'montant_accorde', 'statut', 'date_creation', 'date_decaissement',
            'admin_decaisseur', 'admin_decaisseur_nom',
            'montant_total_rembourse', 'solde_restant_du', 'est_en_retard',
            'progression_remboursement'
        ]
    
    def get_progression_remboursement(self, obj):
        """Calcule le pourcentage de progression du remboursement"""
        if hasattr(obj.demande, 'conditions_remboursement'):
            total_du = obj.demande.duree_pret * obj.demande.conditions_remboursement.montant_mensualite
            if total_du > 0:
                progression = (obj.montant_total_rembourse / total_du) * 100
                return min(progression, 100)
        return 0


class RepaymentScheduleSerializer(serializers.ModelSerializer):
    """Serializer pour les échéances de remboursement"""
    loan_info = serializers.CharField(source='loan.__str__', read_only=True)
    client_nom = serializers.CharField(source='loan.client.nom_complet', read_only=True)
    montant_total_du = serializers.ReadOnlyField()
    jours_retard = serializers.ReadOnlyField()
    est_en_retard = serializers.SerializerMethodField()
    
    class Meta:
        model = RepaymentSchedule
        fields = [
            'id', 'loan', 'loan_info', 'client_nom', 'numero_echeance',
            'date_echeance', 'montant_mensualite', 'montant_capital',
            'montant_interet', 'solde_restant', 'statut', 'date_paiement',
            'montant_penalites', 'montant_total_du', 'jours_retard', 'est_en_retard'
        ]
    
    def get_est_en_retard(self, obj):
        """Vérifie si l'échéance est en retard"""
        return obj.jours_retard > 0 and obj.statut == 'en_attente'


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer pour les paiements de remboursement"""
    loan_info = serializers.CharField(source='loan.__str__', read_only=True)
    client_nom = serializers.CharField(source='loan.client.nom_complet', read_only=True)
    echeance_info = serializers.CharField(source='echeance.__str__', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'loan', 'loan_info', 'client_nom', 'echeance', 'echeance_info',
            'montant_paye', 'montant_mensualite', 'montant_penalites',
            'transaction_mobile_money', 'statut', 'date_paiement',
            'date_confirmation', 'reference_externe'
        ]
        extra_kwargs = {
            'reference_externe': {'read_only': True},
        }


# =============================================================================
# SERIALIZERS POUR ACTIONS PERSONNALISÉES
# =============================================================================

class EligibilityCheckSerializer(serializers.Serializer):
    """Serializer pour vérifier l'éligibilité d'un client"""
    client_id = serializers.UUIDField(
        help_text="ID du client à vérifier"
    )


class EligibilityResponseSerializer(serializers.Serializer):
    """Serializer pour la réponse de vérification d'éligibilité"""
    eligible = serializers.BooleanField()
    raison = serializers.CharField()
    details_compte = serializers.DictField(required=False)


class ExaminerDemandeSerializer(serializers.Serializer):
    """Serializer pour l'examen d'une demande par le superviseur"""
    commentaires = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        help_text="Commentaires du superviseur lors de l'examen"
    )
    decision = serializers.ChoiceField(
        choices=[('examiner', 'Examiner'), ('rejeter', 'Rejeter')],
        help_text="Décision du superviseur"
    )
    raison_rejet = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        help_text="Raison du rejet si applicable"
    )


class DefinirConditionsSerializer(serializers.Serializer):
    """Serializer pour définir les conditions de remboursement"""
    taux_interet_annuel = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal('0.00'),
        max_value=Decimal('50.00'),
        help_text="Taux d'intérêt annuel en pourcentage"
    )
    jour_echeance_mensuelle = serializers.IntegerField(
        min_value=1,
        max_value=31,
        help_text="Jour du mois pour les échéances (1-31)"
    )
    taux_penalite_quotidien = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal('0.00'),
        max_value=Decimal('10.00'),
        help_text="Taux de pénalité par jour de retard en pourcentage"
    )


class TransfererAdminSerializer(serializers.Serializer):
    """Serializer pour le transfert obligatoire à l'admin"""
    commentaires_transfert = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        help_text="Commentaires pour l'admin"
    )
    confirmer_transfert = serializers.BooleanField(
        default=True,
        help_text="Confirmation du transfert à l'admin"
    )


class ValidationAdminSerializer(serializers.Serializer):
    """Serializer pour la validation finale par l'admin"""
    decision = serializers.ChoiceField(
        choices=[('accorder', 'Accorder'), ('rejeter', 'Rejeter')],
        help_text="Décision finale de l'admin"
    )
    commentaires = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        help_text="Commentaires de l'admin"
    )
    raison_rejet = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        help_text="Raison du rejet si applicable"
    )
    montant_accorde = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        help_text="Montant accordé (peut différer du montant demandé)"
    )


class MarquerDecaisseSerializer(serializers.Serializer):
    """Serializer pour marquer un prêt comme décaissé"""
    confirmer_decaissement = serializers.BooleanField(
        default=True,
        help_text="Confirmation du décaissement physique"
    )
    commentaires = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text="Commentaires sur le décaissement"
    )


class EffectuerRemboursementSerializer(serializers.Serializer):
    """Serializer pour effectuer un remboursement via Mobile Money"""
    echeance_id = serializers.UUIDField(
        help_text="ID de l'échéance à rembourser"
    )
    numero_mobile_money = serializers.CharField(
        max_length=15,
        help_text="Numéro de téléphone Mobile Money"
    )
    operateur = serializers.ChoiceField(
        choices=[('mtn', 'MTN'), ('moov', 'Moov'), ('orange', 'Orange')],
        default='mtn',
        help_text="Opérateur Mobile Money"
    )
    montant_paye = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Montant à payer (mensualité + pénalités éventuelles)"
    )


class ScoreFiabiliteSerializer(serializers.Serializer):
    """Serializer pour le score de fiabilité d'un client"""
    client_id = serializers.UUIDField(
        help_text="ID du client"
    )
    score = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        read_only=True
    )
    details = serializers.DictField(
        read_only=True,
        help_text="Détails du calcul du score"
    )


class CalendrierRemboursementSerializer(serializers.Serializer):
    """Serializer pour afficher le calendrier de remboursement"""
    echeances = RepaymentScheduleSerializer(many=True, read_only=True)
    resume = serializers.DictField(read_only=True)
    statistiques = serializers.DictField(read_only=True)


# =============================================================================
# SERIALIZERS DE RÉPONSE
# =============================================================================

class LoanApplicationResponseSerializer(serializers.Serializer):
    """Serializer pour les réponses d'actions sur les demandes"""
    success = serializers.BooleanField()
    message = serializers.CharField()
    demande = LoanApplicationSerializer(required=False)
    loan = LoanSerializer(required=False)
    conditions = LoanTermsSerializer(required=False)
    next_step = serializers.CharField(required=False)


class StatistiquesPretsSerializer(serializers.Serializer):
    """Serializer pour les statistiques des prêts"""
    total_demandes = serializers.IntegerField()
    demandes_en_cours = serializers.IntegerField()
    prets_accordes = serializers.IntegerField()
    prets_decaisses = serializers.IntegerField()
    montant_total_accorde = serializers.DecimalField(max_digits=15, decimal_places=2)
    montant_total_rembourse = serializers.DecimalField(max_digits=15, decimal_places=2)
    taux_approbation = serializers.DecimalField(max_digits=5, decimal_places=2)
    prets_en_retard = serializers.IntegerField()
    evolution_mensuelle = serializers.ListField()


# =============================================================================
# SERIALIZERS POUR RAPPORTS
# =============================================================================

class RapportDemandeSerializer(serializers.Serializer):
    """Serializer pour le rapport détaillé d'une demande"""
    demande = LoanApplicationSerializer()
    score_fiabilite_details = serializers.DictField()
    conditions_remboursement = LoanTermsSerializer(required=False)
    historique_workflow = serializers.ListField()
    recommandations = serializers.ListField()
    documents_analyses = serializers.DictField()


class ExportDemandesSerializer(serializers.Serializer):
    """Serializer pour l'export des demandes"""
    format = serializers.ChoiceField(
        choices=[('csv', 'CSV'), ('excel', 'Excel'), ('pdf', 'PDF')],
        default='csv'
    )
    date_debut = serializers.DateField(required=False)
    date_fin = serializers.DateField(required=False)
    statuts = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    include_documents = serializers.BooleanField(default=False)
