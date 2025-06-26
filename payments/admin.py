"""
Administration Django pour le module Payments KKiaPay
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import KKiaPayTransaction


@admin.register(KKiaPayTransaction)
class KKiaPayTransactionAdmin(admin.ModelAdmin):
    """
    Interface d'administration pour les transactions KKiaPay
    """
    
    list_display = [
        'reference_tontiflex', 'user', 'type_transaction', 'montant_display', 
        'status_badge', 'numero_telephone', 'created_at'
    ]
    list_filter = [
        'status', 'type_transaction', 'devise', 'webhook_received', 'created_at'
    ]
    search_fields = [
        'reference_tontiflex', 'reference_kkiapay', 'user__username', 
        'numero_telephone', 'description'
    ]
    readonly_fields = [
        'id', 'reference_tontiflex', 'reference_kkiapay', 'created_at', 
        'updated_at', 'processed_at', 'kkiapay_response', 'webhook_data'
    ]
    
    fieldsets = (
        ('Informations générales', {
            'fields': (
                'id', 'reference_tontiflex', 'reference_kkiapay', 
                'type_transaction', 'status'
            )
        }),
        ('Détails financiers', {
            'fields': (
                'montant', 'devise', 'numero_telephone', 'description'
            )
        }),
        ('Utilisateur et contexte', {
            'fields': (
                'user', 'objet_id', 'objet_type'
            )
        }),
        ('Réponses API', {
            'fields': (
                'kkiapay_response', 'webhook_received', 'webhook_data'
            ),
            'classes': ('collapse',)
        }),
        ('Erreurs', {
            'fields': (
                'error_code', 'error_message'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at', 'updated_at', 'processed_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def montant_display(self, obj):
        """Affichage formaté du montant"""
        return f"{obj.montant:,.0f} {obj.devise}"
    montant_display.short_description = "Montant"
    
    def status_badge(self, obj):
        """Badge coloré pour le statut"""
        colors = {
            'pending': '#ffc107',     # Jaune
            'processing': '#17a2b8',  # Bleu
            'success': '#28a745',     # Vert
            'failed': '#dc3545',      # Rouge
            'cancelled': '#6c757d',   # Gris
            'refunded': '#fd7e14',    # Orange
        }
        
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Statut"
    status_badge.admin_order_field = 'status'
    
    def get_queryset(self, request):
        """Optimise les requêtes avec select_related"""
        return super().get_queryset(request).select_related('user')
    
    def has_add_permission(self, request):
        """Désactive l'ajout manuel (les transactions sont créées via l'API)"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Désactive la suppression (pour traçabilité)"""
        return False
