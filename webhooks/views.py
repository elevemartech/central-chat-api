import logging
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import AllowAny
from accounts.models import Account
from .tasks import process_uazapi_event

logger = logging.getLogger(__name__)


class UazapiWebhookView(APIView):
    """
    Recebe eventos do uazapi via POST.
    URL: POST /api/webhook/uazapi/{instance_id}/?token={uazapi_token}

    Autenticação: token na query string (configurado no painel do uazapi).
    Não usa JWT — é chamado pelo servidor do uazapi, não pelo frontend.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, instance_id):
        token = request.query_params.get("token", "")

        try:
            account = Account.objects.get(uazapi_instance=instance_id, uazapi_token=token)
        except Account.DoesNotExist:
            logger.warning("Webhook recebido com token inválido para instância %s", instance_id)
            return Response({"detail": "Unauthorized"}, status=401)

        event = request.data.get("event") or request.data.get("type", "")
        logger.info("Webhook recebido: instance=%s event=%s", instance_id, event)

        # Enfileira processamento assíncrono — responde imediatamente ao uazapi
        process_uazapi_event.delay(str(account.id), request.data)

        return Response({"status": "received"})
