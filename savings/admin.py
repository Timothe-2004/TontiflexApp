from django.contrib import admin
from .models import SavingsAccount, SavingsTransaction


@admin.register(SavingsAccount)
class SavingsAccountAdmin(admin.ModelAdmin):
    """
    Configuration d'administration pour les comptes épargne
    """
    list_display = [
        'id', 'client', 'statut', 'date_demande', 
        'agent_validateur', 'date_activation', 'calculer_solde'
    ]
    list_filter = [
        'statut', 'operateur_mobile_money',
        'date_demande', 'date_activation'
    ]
    search_fields = [
        'client__nom', 'client__prenom', 'client__telephone',
        'numero_telephone', 'commentaires'
    ]
    readonly_fields = [
        'id', 'date_demande', 'date_validation_agent', 
        'date_paiement_frais', 'date_activation', 'calculer_solde'
    ]
    fieldsets = (
        ('Informations Client', {
            'fields': ('client', 'statut')
        }),
        ('Documents d\'Identité', {
            'fields': ('piece_identite', 'photo_identite')
        }),
        ('Mobile Money', {
            'fields': ('numero_telephone', 'operateur_mobile_money')
        }),
        ('Validation Agent', {
            'fields': ('agent_validateur', 'date_validation_agent', 'commentaires_agent')
        }),
        ('Paiement et Activation', {
            'fields': ('transaction_creation', 'date_paiement_frais', 'date_activation')
        }),
        ('Métadonnées', {
            'fields': ('date_demande', 'commentaires', 'calculer_solde'),
            'classes': ('collapse',)
        })
    )
    
    def calculer_solde(self, obj):
        """Affiche le solde calculé dans l'admin"""
        return f"{obj.calculer_solde()} FCFA"
    calculer_solde.short_description = "Solde Actuel"


@admin.register(SavingsTransaction)
class SavingsTransactionAdmin(admin.ModelAdmin):
    """
    Configuration d'administration pour les transactions épargne
    """
    list_display = [
        'id', 'compte_epargne', 'type_transaction', 'montant',
        'statut', 'date_transaction'
    ]
    list_filter = [
        'type_transaction', 'statut', 'date_transaction'
    ]
    search_fields = [
        'compte_epargne__client__nom', 'compte_epargne__client__prenom',
        'description', 'reference_externe'
    ]
    readonly_fields = [
        'id', 'date_transaction'
    ]
    fieldsets = (
        ('Transaction', {
            'fields': ('compte_epargne', 'type_transaction', 'montant', 'statut')
        }),
        ('Mobile Money', {
            'fields': ('transaction_mobile_money',)
        }),
        ('Détails', {
            'fields': ('description', 'reference_externe')
        }),
        ('Métadonnées', {
            'fields': ('date_transaction',),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Optimise les requêtes avec select_related"""
        return super().get_queryset(request).select_related(
            'compte_epargne', 'compte_epargne__client', 'transaction_mobile_money'
        )
