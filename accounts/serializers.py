from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Client, AgentSFD, SuperviseurSFD, AdministrateurSFD, AdminPlateforme, SFD

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


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    motDePasse = serializers.CharField(write_only=True)


class SFDSerializer(serializers.ModelSerializer):
    class Meta:
        model = SFD
        fields = ['id', 'nom', 'adresse', 'telephone', 'email', 'numeroMobileMoney']

    def validate_id(self, value):
        if SFD.objects.filter(id=value).exists():
            raise serializers.ValidationError("Une SFD avec cet ID existe déjà")
        return value

class SFDDetailSerializer(SFDSerializer):
    nombre_agents = serializers.SerializerMethodField()
    nombre_superviseurs = serializers.SerializerMethodField()
    nombre_administrateurs = serializers.SerializerMethodField()

    class Meta(SFDSerializer.Meta):
        fields = SFDSerializer.Meta.fields + [
            'dateCreation', 'nombre_agents', 'nombre_superviseurs', 'nombre_administrateurs'
        ]

    def get_nombre_agents(self, obj):
        return obj.agents_sfd.count()

    def get_nombre_superviseurs(self, obj):
        return obj.superviseurs_sfd.count()

    def get_nombre_administrateurs(self, obj):
        return obj.administrateurs_sfd.count()
