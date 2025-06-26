# 🔐 Guide d'Authentification Swagger pour TontiFlex

## 📋 Étapes pour s'Authentifier dans Swagger

### **Étape 1: Tester l'Endpoint de Connexion**
1. Ouvrez votre navigateur sur http://localhost:8000/api/schema/swagger-ui/
2. Cherchez l'endpoint `POST /auth/login/` dans la section "🔐 Authentification"
3. Cliquez sur "Try it out"
4. Remplissez les champs :
   ```json
   {
     "email": "test@example.com",
     "motDePasse": "testpass123"
   }
   ```
5. Cliquez sur "Execute"

### **Étape 2: Récupérer le Token**
Si la connexion réussit, vous recevrez une réponse comme :
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "id": 2,
    "email": "test@example.com",
    "username": "testuser",
    "is_active": true
  }
}
```

**Copiez la valeur du champ `access`** (le token d'accès)

### **Étape 3: Authentifier dans Swagger**
1. **Cliquez sur le bouton "Authorize" 🔒** en haut à droite de la page Swagger
2. Dans la popup qui s'ouvre, vous verrez un champ **"jwtAuth (http, Bearer)"**
3. Dans le champ "Value", entrez :
   ```
   Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ```
   ⚠️ **Important**: Mettez `Bearer ` (avec un espace) suivi de votre token
4. Cliquez sur **"Authorize"**
5. Cliquez sur **"Close"**

### **Étape 4: Tester les Endpoints Protégés**
Maintenant tous vos appels API utiliseront automatiquement ce token. Vous pouvez tester :
- `GET /api/savings/accounts/` (Comptes épargne)
- `GET /api/savings/transactions/` (Transactions)
- `POST /api/savings/create-request/` (Créer une demande)

## 🔧 Dépannage

### **Erreur "Failed to fetch"**
Cela arrive quand :
- Le serveur Django n'est pas démarré
- Problème CORS
- URL incorrecte

**Solution** : Vérifiez que le serveur tourne sur http://localhost:8000

### **Erreur 401 "Unauthorized"**
Cela arrive quand :
- Token expiré (15 minutes)
- Token mal formaté
- Pas de token fourni

**Solution** : Refaire la connexion et récupérer un nouveau token

### **Erreur 403 "Forbidden"**
Cela arrive quand :
- L'utilisateur n'a pas les permissions requises
- Mauvais type d'utilisateur (client vs agent vs admin)

**Solution** : Vérifier que votre utilisateur a le bon rôle

## 👥 Types d'Utilisateurs et Permissions

### **Client**
- Peut créer des demandes de compte épargne
- Peut voir ses propres transactions
- Peut effectuer des dépôts/retraits

### **Agent SFD** 
- Peut valider les demandes de création de compte
- Peut voir les comptes/transactions de sa SFD
- Peut approuver les retraits

### **Admin SFD**
- Toutes les permissions de l'Agent SFD
- Peut gérer les statistiques
- Peut suspendre des comptes

## 🧪 Comptes de Test Disponibles

Pour tester différents rôles, vous pouvez créer des utilisateurs :

```python
# Client
python manage.py shell -c "
from django.contrib.auth import get_user_model; 
User = get_user_model(); 
user = User.objects.create_user(
    username='client1', 
    email='client@test.com', 
    password='test123'
);
from accounts.models import Client;
Client.objects.create(
    user=user,
    nom='Test',
    prenom='Client',
    telephone='+22970000001'
)"
```

## 📞 Support

Si vous rencontrez des problèmes :
1. Vérifiez que le serveur Django est démarré
2. Vérifiez que le token est bien copié avec "Bearer "
3. Vérifiez les logs du serveur pour voir les erreurs détaillées
