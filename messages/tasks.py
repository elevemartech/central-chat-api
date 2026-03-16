import logging
from celery import shared_task
from django.utils.timezone import now
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_outbound_message(self, conversation_id, message_type, content, quoted_message_id=""):
    """Envia mensagem de texto para o uazapi e persiste no banco."""
    from conversations.models import Conversation
    from .models import Message

    try:
        conversation = Conversation.objects.select_related("account", "contact").get(id=conversation_id)
        account = conversation.account
        contact_phone = conversation.contact.phone

        base_url = settings.UAZAPI_BASE_URL.rstrip("/")
        headers = {"token": account.uazapi_token, "Content-Type": "application/json"}

        if message_type == Message.MessageType.TEXT:
            payload = {
                "number": contact_phone,
                "text": content,
            }
            if quoted_message_id:
                payload["quotedMsgId"] = quoted_message_id

            response = httpx.post(
                f"{base_url}/message/sendText/{account.uazapi_instance}",
                json=payload,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            Message.objects.create(
                conversation=conversation,
                uazapi_message_id=data.get("key", {}).get("id"),
                direction=Message.Direction.OUTBOUND,
                message_type=Message.MessageType.TEXT,
                status=Message.Status.SENT,
                content=content,
                quoted_message_id=quoted_message_id,
                timestamp=now(),
            )

            # Atualiza conversa
            conversation.last_message_at = now()
            conversation.last_message_preview = content[:100]
            conversation.save(update_fields=["last_message_at", "last_message_preview"])

    except httpx.HTTPError as exc:
        logger.error("Erro ao enviar mensagem: %s", exc)
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.exception("Erro inesperado ao enviar mensagem")
        raise
