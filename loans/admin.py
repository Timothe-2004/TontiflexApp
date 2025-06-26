"""
ADMINISTRATION DJANGO POUR LE MODULE PRÊTS - TONTIFLEX

Configuration de l'interface d'administration pour:
1. Demandes de prêt avec workflow
2. Conditions de remboursement
3. Prêts accordés et suivi
4. Échéances et calendriers
5. Paiements Mobile Money
6. Rapports et statisti    list_display = [
        'id', 'loan', 'numero_echeance', 'date_echeance',
        'montant_mensualite', 'statut'
    ]
    
    list_filter = [
        'statut', 'date_echeance', 'loan__statut'
    ]
    
    search_fields = [
        'loan__client__nom', 'loan__client__prenom'
    ]
    
    readonly_fields = [
        'id', 'montant_capital', 'montant_interet', 'solde_restant'
    ]e intuitive pour les administrateurs
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.db.models import Sum, Count
from .models import LoanApplication, LoanTerms, Loan, RepaymentSchedule, Payment


# =============================================================================
# DEMANDES DE PRÊT
# =============================================================================

@admin.register(LoanApplication)
class LoanApplicationAdmin(admin.ModelAdmin):
    """Administration des demandes de prêt."""
    
    list_display = [
        'id', 'client_nom', 'montant_souhaite', 'statut_colored', 
        'score_fiabilite', 'date_soumission', 'superviseur_examinateur', 'admin_validateur'
    ]
    
    list_filter = [
        'statut', 'type_pret', 'date_soumission', 'date_examen_superviseur',
        'date_validation_admin'
    ]
    
    search_fields = [
        'client__nom', 'client__prenom', 'client__telephone', 'client__email',
        'objet_pret'
    ]
    
    readonly_fields = [
        'id', 'date_soumission', 'score_fiabilite', 'details_score_display',
        'date_examen_superviseur', 'date_validation_admin'
    ]
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('id', 'client', 'date_soumission', 'statut')
        }),
        ('Demande de prêt', {
            'fields': (
                'montant_souhaite', 'duree_pret', 'type_pret', 'objet_pret',
                'documents_justificatifs'
            )
        }),
        ('Situation du demandeur', {
            'fields': (
                'revenus_mensuel', 'charges_mensuelles', 'ratio_endettement',
                'situation_familiale', 'situation_professionnelle',
                'nombre_personnes_charge'
            )
        }),
        ('Évaluation', {
            'fields': ('score_fiabilite', 'details_score_display')
        }),
        ('Traitement Superviseur', {
            'fields': (
                'superviseur_traitant', 'date_traitement_superviseur',
                'commentaire_superviseur'
            )
        }),
        ('Validation Admin', {
            'fields': (
                'admin_validateur', 'date_traitement_admin',
                'commentaire_admin'
            )
        })
    )
    
    def client_nom(self, obj):
        """Affiche le nom complet du client."""
        return obj.client.nom_complet if obj.client else "N/A"
    client_nom.short_description = "Client"
    client_nom.admin_order_field = 'client__nom'
    
    def statut_colored(self, obj):
        """Affiche le statut avec couleur."""
        colors = {
            'soumis': '#ffc107',  # jaune
            'en_cours_examen': '#17a2b8',  # bleu
            'transfere_admin': '#fd7e14',  # orange
            'accorde': '#28a745',  # vert
            'rejete': '#dc3545'  # rouge
        }
        color = colors.get(obj.statut, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_statut_display()
        )
    statut_colored.short_description = "Statut"
    statut_colored.admin_order_field = 'statut'
    
    def details_score_display(self, obj):
        """Affiche les détails du score de manière lisible."""
        if obj.details_score:
            details = obj.details_score
            html = f"<strong>Score: {details.get('score', 'N/A')}/100</strong><br>"
            html += f"Évaluation: {details.get('evaluation', 'N/A')}<br>"
            if details.get('details'):
                html += "<ul>"
                for key, value in details['details'].items():
                    html += f"<li>{key}: {value}</li>"
                html += "</ul>"
            return mark_safe(html)
        return "Aucun détail"
    details_score_display.short_description = "Détails du score"
    
    def get_queryset(self, request):
        """Optimise les requêtes."""
        return super().get_queryset(request).select_related(
            'client', 'superviseur_traitant', 'admin_validateur'
        )


# =============================================================================
# CONDITIONS DE REMBOURSEMENT
# =============================================================================

@admin.register(LoanTerms)
class LoanTermsAdmin(admin.ModelAdmin):
    """Administration des conditions de remboursement."""
    
    list_display = [
        'id', 'demande_client', 'taux_interet_annuel',
        'montant_mensualite', 'superviseur_definisseur', 'date_creation'
    ]
    
    list_filter = [
        'taux_interet_annuel', 'date_creation', 'superviseur_definisseur'
    ]
    
    search_fields = [
        'demande__client__nom', 'demande__client__prenom',
        'superviseur_definisseur__nom', 'superviseur_definisseur__prenom'
    ]
    
    readonly_fields = [
        'id', 'date_creation', 'montant_mensualite'
    ]
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('id', 'demande', 'definies_par', 'date_creation')
        }),
        ('Conditions de prêt', {
            'fields': (
                'montant_accorde', 'taux_interet_annuel', 'duree_mois',
                'date_premiere_echeance'
            )
        }),
        ('Calculs automatiques', {
            'fields': (
                'montant_mensualite', 'cout_total_credit', 'cout_interet_total'
            ),
            'classes': ('collapse',)
        })
    )
    
    def demande_client(self, obj):
        """Affiche le client de la demande."""
        return obj.demande.client.nom_complet if obj.demande and obj.demande.client else "N/A"
    demande_client.short_description = "Client"
    demande_client.admin_order_field = 'demande__client__nom'


# =============================================================================
# PRÊTS ACCORDÉS
# =============================================================================

@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    """Administration des prêts accordés."""
    
    list_display = [
        'id', 'client_nom', 'montant_accorde', 'statut_colored',
        'date_creation', 'date_decaissement'
    ]
    
    list_filter = [
        'statut', 'date_creation', 'date_decaissement'
    ]
    
    search_fields = [
        'client__nom', 'client__prenom', 'client__telephone',
        'demande__objet_pret'
    ]
    
    readonly_fields = [
        'id', 'date_creation'
    ]
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('id', 'reference', 'demande', 'client', 'date_creation')
        }),
        ('Conditions du prêt', {
            'fields': (
                'montant_accorde', 'taux_interet_annuel', 'duree_mois',
                'montant_mensualite'
            )
        }),
        ('Statut et dates', {
            'fields': (
                'statut', 'date_decaissement', 'date_premiere_echeance',
                'admin_validateur'
            )
        }),
        ('Suivi des remboursements', {
            'fields': (
                'montant_total_remboursement', 'montant_rembourse',
                'montant_restant', 'progress_bar'
            ),
            'classes': ('collapse',)
        })
    )
    
    def client_nom(self, obj):
        """Affiche le nom du client."""
        return obj.client.nom_complet if obj.client else "N/A"
    client_nom.short_description = "Client"
    client_nom.admin_order_field = 'client__nom'
    
    def statut_colored(self, obj):
        """Affiche le statut avec couleur."""
        colors = {
            'accorde': '#ffc107',  # jaune
            'decaisse': '#17a2b8',  # bleu
            'en_remboursement': '#fd7e14',  # orange
            'solde': '#28a745',  # vert
            'en_defaut': '#dc3545'  # rouge
        }
        color = colors.get(obj.statut, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_statut_display()
        )
    statut_colored.short_description = "Statut"
    statut_colored.admin_order_field = 'statut'
    
    def progress_remboursement(self, obj):
        """Affiche le pourcentage de remboursement."""
        if obj.montant_total_remboursement > 0:
            pourcentage = (obj.montant_rembourse / obj.montant_total_remboursement) * 100
            return f"{pourcentage:.1f}%"
        return "0%"
    progress_remboursement.short_description = "Progression"
    
    def progress_bar(self, obj):
        """Affiche une barre de progression."""
        if obj.montant_total_remboursement > 0:
            pourcentage = (obj.montant_rembourse / obj.montant_total_remboursement) * 100
            couleur = '#28a745' if pourcentage >= 75 else '#ffc107' if pourcentage >= 50 else '#dc3545'
            return format_html(
                '<div style="width: 200px; background-color: #e9ecef; border-radius: 4px; overflow: hidden;">'
                '<div style="width: {}%; height: 20px; background-color: {}; text-align: center; line-height: 20px; color: white; font-size: 12px;">'
                '{}%'
                '</div></div>',
                min(pourcentage, 100),
                couleur,
                round(pourcentage, 1)
            )
        return "Aucun remboursement"
    progress_bar.short_description = "Barre de progression"


# =============================================================================
# ÉCHÉANCES DE REMBOURSEMENT
# =============================================================================

@admin.register(RepaymentSchedule)
class RepaymentScheduleAdmin(admin.ModelAdmin):
    """Administration des échéances de remboursement."""
    
    list_display = [
        'id', 'loan', 'numero_echeance', 'date_echeance',
        'montant_mensualite', 'statut'
    ]
    
    list_filter = [
        'statut', 'date_echeance', 'loan__statut'
    ]
    
    search_fields = [
        'loan__client__nom', 'loan__client__prenom'
    ]
    
    readonly_fields = [
        'id', 'montant_capital', 'montant_interet', 'solde_restant'
    ]
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('id', 'pret', 'numero_echeance', 'date_echeance')
        }),
        ('Montants', {
            'fields': (
                'montant_principal', 'montant_interet', 'montant_penalites',
                'montant_total', 'montant_paye', 'montant_restant'
            )
        }),
        ('Statut', {
            'fields': ('statut', 'jours_retard_calcul', 'date_paiement')
        })
    )
    
    def pret_reference(self, obj):
        """Affiche la référence du prêt."""
        return obj.pret.reference if obj.pret else "N/A"
    pret_reference.short_description = "Référence prêt"
    pret_reference.admin_order_field = 'pret__reference'
    
    def statut_colored(self, obj):
        """Affiche le statut avec couleur."""
        colors = {
            'prevu': '#6c757d',  # gris
            'en_retard': '#dc3545',  # rouge
            'paye': '#28a745',  # vert
            'paye_partiel': '#ffc107'  # jaune
        }
        color = colors.get(obj.statut, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_statut_display()
        )
    statut_colored.short_description = "Statut"
    statut_colored.admin_order_field = 'statut'
    
    def jours_retard_calcul(self, obj):
        """Calcule et affiche les jours de retard."""
        return obj.jours_retard
    jours_retard_calcul.short_description = "Jours de retard"


# =============================================================================
# PAIEMENTS
# =============================================================================

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Administration des paiements."""
    
    list_display = [
        'id', 'loan', 'montant_paye', 'statut',
        'date_paiement'
    ]
    
    list_filter = [
        'statut', 'date_paiement'
    ]
    
    search_fields = [
        'loan__client__nom', 'loan__client__prenom',
        'reference_externe'
    ]
    
    readonly_fields = [
        'id', 'date_paiement'
    ]
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('id', 'echeance', 'montant', 'date_creation')
        }),
        ('Mobile Money', {
            'fields': (
                'numero_telephone', 'statut_mobile_money',
                'reference_mobile_money', 'reference_externe',
                'date_confirmation', 'commentaire_mobile_money'
            )
        }),
        ('Validation', {
            'fields': ('confirme_par',)
        })
    )
    
    def echeance_info(self, obj):
        """Affiche les infos de l'échéance."""
        if obj.echeance:
            return f"{obj.echeance.pret.reference} - Échéance #{obj.echeance.numero_echeance}"
        return "N/A"
    echeance_info.short_description = "Échéance"
    echeance_info.admin_order_field = 'echeance__numero_echeance'
    
    def statut_mobile_money_colored(self, obj):
        """Affiche le statut Mobile Money avec couleur."""
        colors = {
            'en_attente': '#6c757d',  # gris
            'en_cours': '#17a2b8',  # bleu
            'confirme': '#28a745',  # vert
            'echec': '#dc3545',  # rouge
            'expire': '#ffc107'  # jaune
        }
        color = colors.get(obj.statut_mobile_money, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_statut_mobile_money_display()
        )
    statut_mobile_money_colored.short_description = "Statut Mobile Money"
    statut_mobile_money_colored.admin_order_field = 'statut_mobile_money'


# =============================================================================
# ACTIONS PERSONNALISÉES
# =============================================================================

def export_demandes_csv(modeladmin, request, queryset):
    """Exporte les demandes sélectionnées en CSV."""
    # À implémenter selon les besoins
    pass
export_demandes_csv.short_description = "Exporter en CSV"

def marquer_paiements_confirmes(modeladmin, request, queryset):
    """Marque les paiements sélectionnés comme confirmés."""
    updated = queryset.filter(statut_mobile_money='en_cours').update(
        statut_mobile_money='confirme'
    )
    modeladmin.message_user(
        request,
        f"{updated} paiement(s) marqué(s) comme confirmé(s)."
    )
marquer_paiements_confirmes.short_description = "Marquer comme confirmés"

# Ajouter les actions aux admins
LoanApplicationAdmin.actions = [export_demandes_csv]
PaymentAdmin.actions = [marquer_paiements_confirmes]


# =============================================================================
# CONFIGURATION GLOBALE
# =============================================================================

# Personnalisation de l'interface admin
admin.site.site_header = "TontiFlex - Administration des Prêts"
admin.site.site_title = "TontiFlex Prêts"
admin.site.index_title = "Gestion des Prêts et Remboursements"
