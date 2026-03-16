import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from accounts.models import Account
from .tasks import process_uazapi_event

logger = logging.getLogger(__name__)


class UazapiWebhookView(APIView):
    """
    Recebe eventos do uazapi via POST.
    URL: POST /api/webhook/uazapi/

    Autenticação: o uazapi envia o token da instância dentro do body ou header.
    A conta é identificada pelo token — sem instance_id na URL, sem query params.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        # Tenta encontrar o token em diferentes lugares que o uazapi pode enviar
        token = (
            request.data.get("token")
            or request.data.get("instanceToken")
            or request.headers.get("token", "")
        )

        if not token:
            logger.warning("Webhook recebido sem token")
            return Response({"detail": "Token ausente"}, status=400)

        try:
            account = Account.objects.get(uazapi_token=token)
        except Account.DoesNotExist:
            logger.warning("Webhook recebido com token desconhecido: %s", token[:10])
            return Response({"detail": "Unauthorized"}, status=401)

        event = request.data.get("event") or request.data.get("type", "")
        logger.info("Webhook recebido: instance=%s event=%s", account.uazapi_instance, event)

        # Enfileira processamento assíncrono — responde imediatamente ao uazapi
        process_uazapi_event.delay(str(account.id), request.data)

        return Response({"status": "received"})