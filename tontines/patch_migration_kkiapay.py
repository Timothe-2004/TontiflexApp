# PATCH POUR MIGRATION KKIAPAY - Remplace les imports mobile_money
# Ce fichier doit être appliqué au modèle tontines/models.py

# 1. Remplacer toutes les références transaction_mobile_money par transaction_kkiapay
# 2. Changer les imports mobile_money vers payments.KKiaPayTransaction
# 3. Mettre à jour les méthodes de paiement

# RECHERCHE-REMPLACE pour tontines/models.py :

"""
Remplacements à effectuer:

1. Ligne 772: 
   ANCIEN: transaction_mobile_money = models.ForeignKey('mobile_money.TransactionMobileMoney',...)
   NOUVEAU: transaction_kkiapay = models.ForeignKey('payments.KKiaPayTransaction',...)

2. Ligne 921: Supprimer l'import mobile_money.services_adhesion

3. Ligne 928: Supprimer l'import mobile_money.models.TransactionMobileMoney  

4. Lignes 1150-1151: 
   ANCIEN: transaction_mobile_money = models.ForeignKey('mobile_money.TransactionMobileMoney',...)
   NOUVEAU: transaction_kkiapay = models.ForeignKey('payments.KKiaPayTransaction',...)

5. Lignes 1277-1278: 
   ANCIEN: transaction_mobile_money = models.ForeignKey('mobile_money.TransactionMobileMoney',...)
   NOUVEAU: transaction_kkiapay = models.ForeignKey('payments.KKiaPayTransaction',...)

6. Méthodes des classes Adhesion, Cotisation, Retrait: 
   Remplacer les références mobile_money par KKiaPay
"""

# NOUVEAU CONTENU POUR LES MÉTHODES CRITIQUES:

def initier_paiement_kkiapay(self):
    """Initie le paiement des frais d'adhésion via KKiaPay - NOUVELLE VERSION"""
    if self.statut_actuel != 'validee_agent':
        raise ValidationError("La demande doit être validée par un agent avant le paiement")
    
    # Utiliser le service de migration KKiaPay
    from payments.services_migration import migration_service
    
    transaction_data = {
        'user': self.client.user,
        'montant': self.frais_adhesion_calcules,
        'telephone': self.numero_telephone_paiement,
        'adhesion_id': self.id,
        'description': f"Frais adhésion tontine - {self.client.prenom} {self.client.nom}"
    }
    
    transaction_kkia = migration_service.create_tontine_adhesion_transaction(transaction_data)
    
    # Associer la transaction KKiaPay à l'adhésion
    self.transaction_kkiapay = transaction_kkia
    self.statut_actuel = 'en_cours_paiement'
    self.save()
    
    logger.info(f"Paiement KKiaPay initié pour la demande {self.id}")
    return {
        'success': True,
        'transaction_id': transaction_kkia.id,
        'reference': transaction_kkia.reference_tontiflex
    }

def confirmer_paiement_kkiapay(self, montant_paye, reference_paiement, transaction_kkia=None):
    """Confirme le paiement des frais d'adhésion via KKiaPay - NOUVELLE VERSION"""
    if self.statut_actuel not in ['validee_agent', 'en_cours_paiement']:
        raise ValidationError("Paiement non autorisé pour ce statut")
    
    self.frais_adhesion_payes = montant_paye
    self.reference_paiement = reference_paiement
    if transaction_kkia:
        self.transaction_kkiapay = transaction_kkia
    self.date_paiement_frais = timezone.now()
    self.statut_actuel = 'paiement_effectue'
    self.save()
    
    # Passer automatiquement à l'étape suivante
    self.finaliser_adhesion()
    logger.info(f"Paiement KKiaPay confirmé pour la demande {self.id} : {montant_paye} FCFA")

# MODÈLES CONCERNÉS:
# - TontineParticipant.transactionAdhesion -> 'payments.KKiaPayTransaction'
# - Adhesion.transaction_mobile_money -> transaction_kkiapay -> 'payments.KKiaPayTransaction'
# - Cotisation.transaction_mobile_money -> transaction_kkiapay -> 'payments.KKiaPayTransaction'  
# - Retrait.transaction_mobile_money -> transaction_kkiapay -> 'payments.KKiaPayTransaction'

# MISE À JOUR À FAIRE DANS services_migration.py:
def create_tontine_adhesion_transaction(self, data):
    """Crée une transaction KKiaPay pour l'adhésion à une tontine"""
    return KKiaPayTransaction.objects.create(
        reference_tontiflex=f"ADHE_{data['adhesion_id']}_{timezone.now().strftime('%Y%m%d_%H%M%S')}",
        type_transaction='adhesion_tontine',
        status='pending',
        montant=data['montant'],
        devise='XOF',
        user=data['user'],
        numero_telephone=data['telephone'],
        description=data['description'],
        metadata={
            'adhesion_id': data['adhesion_id'],
            'type': 'frais_adhesion_tontine'
        }
    )

print("✅ Patch de migration KKiaPay - Instructions pour models.py créé")
