from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Client, AgentSFD, SuperviseurSFD, AdministrateurSFD, AdminPlateforme, SFD

# ============================================================================
# SERIALIZERS POUR INSCRIPTION ET AUTHENTIFICATION
# ============================================================================

class InscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        exclude = [
            'id', 'user', 'scorefiabilite', 'statut', 'dateCreation', 'derniere_connexion', 'email_verifie',
        ]
       

    def create(self, validated_data):
        # Always create as CLIENT
        instance = Client(**validated_data)
        instance.motDePasse = self.initial_data.get('motDePasse')
        instance.set_password(instance.motDePasse)
        instance.save()
        return instance


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    motDePasse = serializers.CharField(write_only=True)


# ============================================================================
# SERIALIZERS POUR LA GESTION DES UTILISATEURS (LECTURE/API)
# ============================================================================

class ClientSerializer(serializers.ModelSerializer):
    """Serializer pour la lecture des clients via API REST"""
    tontines_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Client
        fields = '__all__'
    
    def get_tontines_count(self, obj):
        """Retourne le nombre de tontines auxquelles le client participe"""
        return obj.tontines.count() if hasattr(obj, 'tontines') else 0


class AgentSFDSerializer(serializers.ModelSerializer):
    """Serializer pour la lecture des agents SFD via API REST"""
    sfd_nom = serializers.CharField(source='sfd.nom', read_only=True)
    
    class Meta:
        model = AgentSFD
        fields = '__all__'


class SuperviseurSFDSerializer(serializers.ModelSerializer):
    """Serializer pour la lecture des superviseurs SFD via API REST"""
    sfd_nom = serializers.CharField(source='sfd.nom', read_only=True)
    
    class Meta:
        model = SuperviseurSFD
        fields = '__all__'


class AdministrateurSFDSerializer(serializers.ModelSerializer):
    """Serializer pour la lecture des administrateurs SFD via API REST"""
    sfd_nom = serializers.CharField(source='sfd.nom', read_only=True)
    
    class Meta:
        model = AdministrateurSFD
        fields = '__all__'


class AdminPlateformeSerializer(serializers.ModelSerializer):
    """Serializer pour la lecture des admins plateforme via API REST"""
    
    class Meta:
        model = AdminPlateforme
        fields = '__all__'


class SFDSerializer(serializers.ModelSerializer):
    """Serializer de base pour les SFD"""
    class Meta:
        model = SFD
        fields = '__all__'

    def validate_id(self, value):
        if SFD.objects.filter(id=value).exists():
            raise serializers.ValidationError("Une SFD avec cet ID existe déjà")
        return value


class SFDDetailSerializer(SFDSerializer):
    """Serializer détaillé pour les SFD avec statistiques"""
    nombre_agents = serializers.SerializerMethodField()
    nombre_superviseurs = serializers.SerializerMethodField()
    nombre_administrateurs = serializers.SerializerMethodField()
    nombre_clients = serializers.SerializerMethodField()

    class Meta(SFDSerializer.Meta):
        fields = list(SFDSerializer.Meta.fields) + [
            'dateCreation', 'nombre_agents', 'nombre_superviseurs', 
            'nombre_administrateurs', 'nombre_clients'
        ]

    def get_nombre_agents(self, obj):
        return obj.agents_sfd.count()

    def get_nombre_superviseurs(self, obj):
        return obj.superviseurs_sfd.count()

    def get_nombre_administrateurs(self, obj):
        return obj.administrateurs_sfd.count()
    
    def get_nombre_clients(self, obj):
        # Les clients sont liés aux tontines qui sont liées aux administrateurs SFD
        from tontines.models import TontineParticipant
        return TontineParticipant.objects.filter(
            tontine__administrateurId__sfd=obj
        ).values('client').distinct().count()


# ============================================================================
# SERIALIZERS POUR LA CRÉATION ADMINISTRATIVE
# ============================================================================

# Serializers for admin creation of users (AGENT_SFD, SUPERVISEUR_SFD, ADMIN_TONTINE)

class AgentSFDAdminSerializer(serializers.ModelSerializer):
    sfd_id = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = AgentSFD
        fields = ['nom', 'prenom', 'telephone', 'email', 'adresse', 'profession', 'motDePasse', 'sfd_id', 'est_actif']
        extra_kwargs = {'motDePasse': {'write_only': True}}

    def create(self, validated_data):
        User = get_user_model()
        sfd_id = validated_data.pop('sfd_id')
        try:
            sfd = SFD.objects.get(id=sfd_id)
        except SFD.DoesNotExist:
            raise serializers.ValidationError({'sfd_id': 'SFD introuvable'})
        mot_de_passe = validated_data.pop('motDePasse')
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=mot_de_passe
        )
        agent = AgentSFD.objects.create(user=user, motDePasse=mot_de_passe, sfd=sfd, **validated_data)
        return agent

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['sfd'] = {
            'id': instance.sfd.id,
            'nom': instance.sfd.nom
        } if instance.sfd else None
        return rep


class SuperviseurSFDAdminSerializer(serializers.ModelSerializer):
    sfd_id = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = SuperviseurSFD
        fields = ['nom', 'prenom', 'telephone', 'email', 'adresse', 'profession', 'motDePasse', 'sfd_id', 'est_actif']
        extra_kwargs = {'motDePasse': {'write_only': True}}

    def create(self, validated_data):
        User = get_user_model()
        sfd_id = validated_data.pop('sfd_id')
        try:
            sfd = SFD.objects.get(id=sfd_id)
        except SFD.DoesNotExist:
            raise serializers.ValidationError({'sfd_id': 'SFD introuvable'})
        mot_de_passe = validated_data.pop('motDePasse')
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=mot_de_passe
        )
        superviseur = SuperviseurSFD.objects.create(user=user, motDePasse=mot_de_passe, sfd=sfd, **validated_data)
        return superviseur

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['sfd'] = {
            'id': instance.sfd.id,
            'nom': instance.sfd.nom
        } if instance.sfd else None
        return rep


class AdministrateurSFDAdminSerializer(serializers.ModelSerializer):
    sfd_id = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = AdministrateurSFD
        fields = ['nom', 'prenom', 'telephone', 'email', 'adresse', 'profession', 'motDePasse', 'sfd_id', 'peut_creer_tontines', 'est_actif']
        extra_kwargs = {'motDePasse': {'write_only': True}}

    def create(self, validated_data):
        User = get_user_model()
        sfd_id = validated_data.pop('sfd_id')
        try:
            sfd = SFD.objects.get(id=sfd_id)
        except SFD.DoesNotExist:
            raise serializers.ValidationError({'sfd_id': 'SFD introuvable'})
        mot_de_passe = validated_data.pop('motDePasse')
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=mot_de_passe
        )
        admin = AdministrateurSFD.objects.create(user=user, motDePasse=mot_de_passe, sfd=sfd, **validated_data)
        return admin

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['sfd'] = {
            'id': instance.sfd.id,
            'nom': instance.sfd.nom
        } if instance.sfd else None
        return rep


class AdminPlateformeAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminPlateforme
        fields = ['nom', 'prenom', 'telephone', 'email', 'adresse', 'profession', 'motDePasse', 'peut_gerer_comptes', 'peut_gerer_sfd', 'est_actif']
        extra_kwargs = {'motDePasse': {'write_only': True}}

    def create(self, validated_data):
        User = get_user_model()
        mot_de_passe = validated_data.pop('motDePasse')
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=mot_de_passe
        )
        admin = AdminPlateforme.objects.create(user=user, motDePasse=mot_de_passe, **validated_data)
        return admin
