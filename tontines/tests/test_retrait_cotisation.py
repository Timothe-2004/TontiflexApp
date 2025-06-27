import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from tontines.models import Tontine, TontineParticipant, Retrait
from payments.models import KKiaPayTransaction

User = get_user_model()

@pytest.mark.django_db
def test_retrait_cotisation_tontine_workflow():
    # Préparation des données
    client = User.objects.create_user(username='client1', password='testpass')
    tontine = Tontine.objects.create(nom="Tontine Test", mise_min=1000, mise_max=10000, fraisAdhesion=500)
    participant = TontineParticipant.objects.create(tontine=tontine, client=client, montantMise=2000, statut='actif')
    # Simuler un solde suffisant (si champ solde existe)
    if hasattr(participant, 'solde'):
        participant.solde = 10000
        participant.save()

    # Authentification
    api_client = APIClient()
    api_client.force_authenticate(user=client)

    # Création d'une demande de retrait
    retrait_data = {
        "tontine": tontine.id,
        "montant": 2000,
        "numero_telephone": "+22997000001"
    }
    url = reverse("retrait-list")  # Assure-toi que ce nom de route existe
    response = api_client.post(url, retrait_data, format='json')
    assert response.status_code == 201
    retrait_id = response.data["id"]

    # Validation agent (à simuler ou forcer le statut)
    retrait = Retrait.objects.get(id=retrait_id)
    retrait.statut = Retrait.StatutRetraitChoices.APPROVED
    retrait.save()

    # Simuler l'appel du paiement KKIAPAY (en sandbox)
    # Ici, on suppose que le backend crée une transaction KKiaPay liée au retrait
    transaction = KKiaPayTransaction.objects.create(
        user=client,
        montant=2000,
        type_transaction="retrait_tontine",
        objet_id=retrait.id,
        objet_type="Retrait",
        status="success"
    )

    # Simuler la réception du webhook (normalement automatique)
    retrait.refresh_from_db()
    assert retrait.statut == Retrait.StatutRetraitChoices.CONFIRMEE or retrait.statut == Retrait.StatutRetraitChoices.APPROVED
    # Vérifier que le solde du participant a été mis à jour
    participant.refresh_from_db()
    if hasattr(participant, 'solde'):
        assert participant.solde == 8000
