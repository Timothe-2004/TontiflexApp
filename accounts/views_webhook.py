from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from payments.models import KKiaPayTransaction

@csrf_exempt
def kkiapay_webhook(request):
    if request.method == "POST":
        data = json.loads(request.body)
        transaction_id = data.get("transactionId")
        status = data.get("status")
        # Met à jour la transaction dans la base
        KKiaPayTransaction.objects.filter(reference_tontiflex=transaction_id).update(status=status)
        return JsonResponse({"ok": True})
    return JsonResponse({"error": "Invalid method"}, status=405)
