import logging
from datetime import datetime, timezone
from celery import shared_task
from django.utils.timezone import now
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def process_uazapi_event(self, account_id: str, payload: dict):
    """
    Entry point para todos os eventos do uazapi.
    Estrutura real do payload:
      - payload["EventType"]  → "messages", "chats", "connection", etc.
      - payload["message"]    → dados da mensagem
      - payload["chat"]       → dados do contato/conversa
    """
    event_type = payload.get("EventType", "")

    logger.info("Evento recebido: EventType=%s instance=%s", event_type, payload.get("instanceName", ""))

    try:
        if event_type == "messages":
            handle_incoming_message(account_id, payload)
        elif event_type == "connection":
            status = payload.get("status", "")
            handle_connection_status(account_id, status)
        else:
            logger.debug("Evento ignorado: %s", event_type)
    except Exception as exc:
        logger.exception("Erro ao processar evento %s da conta %s", event_type, account_id)
        raise self.retry(exc=exc)


# ─── Handlers ────────────────────────────────────────────────────────────────

def handle_incoming_message(account_id: str, payload: dict):
    from accounts.models import Account
    from conversations.models import Contact, Conversation
    from chat_messages.models import Message

    message = payload.get("message", {})
    chat = payload.get("chat", {})

    # Ignora mensagens enviadas pela própria conta
    if message.get("fromMe"):
        logger.debug("Ignorando mensagem fromMe")
        return

    # Extrai telefone — remove sufixo @s.whatsapp.net
    raw_chatid = message.get("chatid", "") or message.get("sender_pn", "")
    phone = raw_chatid.replace("@s.whatsapp.net", "").replace("@g.us", "")
    if not phone:
        logger.warning("Telefone não encontrado no payload")
        return

    uazapi_msg_id = message.get("messageid", "") or message.get("id", "")

    # Idempotência — evita duplicatas
    if uazapi_msg_id and Message.objects.filter(uazapi_message_id=uazapi_msg_id).exists():
        logger.debug("Mensagem já processada: %s", uazapi_msg_id)
        return

    account = Account.objects.get(id=account_id)

    # Nome do contato
    push_name = (
        chat.get("wa_name")
        or chat.get("wa_contactName")
        or chat.get("name")
        or message.get("senderName")
        or ""
    )

    # ── Cadastro automático do contato ──────────────────────────────────────
    contact, created = Contact.objects.get_or_create(
        phone=phone,
        defaults={"name": push_name, "push_name": push_name},
    )
    if not created and push_name:
        updated_fields = []
        if not contact.name:
            contact.name = push_name
            updated_fields.append("name")
        if contact.push_name != push_name:
            contact.push_name = push_name
            updated_fields.append("push_name")
        if updated_fields:
            contact.save(update_fields=updated_fields)

    if created:
        logger.info("Novo contato cadastrado: %s (%s)", phone, push_name)

    # ── Cadastro automático da conversa ─────────────────────────────────────
    conversation, conv_created = Conversation.objects.get_or_create(
        account=account,
        contact=contact,
    )
    if conv_created:
        logger.info("Nova conversa criada: conta=%s contato=%s", account.uazapi_instance, phone)

    # ── Tipo e conteúdo da mensagem ──────────────────────────────────────────
    raw_type = message.get("messageType", "") or message.get("type", "text")
    type_map = {
        "ExtendedTextMessage": "text",
        "ImageMessage": "image",
        "AudioMessage": "audio",
        "VideoMessage": "video",
        "DocumentMessage": "document",
        "StickerMessage": "sticker",
        "LocationMessage": "location",
        "ContactMessage": "contact",
        "text": "text",
    }
    message_type = type_map.get(raw_type, "text")
    text_content = message.get("text", "") or ""

    # ── Timestamp ────────────────────────────────────────────────────────────
    ts_raw = message.get("messageTimestamp")
    if ts_raw:
        # uazapi envia em milissegundos
        ts_seconds = int(ts_raw) / 1000 if int(ts_raw) > 1e10 else int(ts_raw)
        timestamp = datetime.fromtimestamp(ts_seconds, tz=timezone.utc)
    else:
        timestamp = now()

    # ── Persiste a mensagem ──────────────────────────────────────────────────
    msg_obj = Message.objects.create(
        conversation=conversation,
        uazapi_message_id=uazapi_msg_id,
        direction="inbound",
        message_type=message_type,
        status="delivered",
        content=text_content,
        timestamp=timestamp,
    )
    logger.info("Mensagem salva: %s | %s | '%s'", phone, message_type, text_content[:50])

    # ── Atualiza conversa ────────────────────────────────────────────────────
    preview = text_content[:100] if text_content else f"[{message_type}]"
    Conversation.objects.filter(id=conversation.id).update(
        last_message_at=timestamp,
        last_message_preview=preview,
        unread_count=conversation.unread_count + 1,
    )

    # ── Push via WebSocket ───────────────────────────────────────────────────
    _push_new_message(conversation, msg_obj)
    _push_conversation_update(conversation, account_id)


def handle_connection_status(account_id: str, status: str):
    from accounts.models import Account
    is_connected = status in ("open", "connected", "onconnected")
    Account.objects.filter(id=account_id).update(is_connected=is_connected)
    logger.info("Conta %s status: %s", account_id, status)


# ─── WebSocket push helpers ───────────────────────────────────────────────────

def _push_new_message(conversation, message):
    from chat_messages.serializers import MessageSerializer
    try:
        group = f"conversation_{conversation.id}"
        async_to_sync(channel_layer.group_send)(
            group,
            {
                "type": "new_message",
                "message": MessageSerializer(message).data,
            },
        )
    except Exception as e:
        logger.warning("WebSocket push falhou (new_message): %s", e)


def _push_message_status(conversation, uazapi_msg_id, new_status):
    try:
        group = f"conversation_{conversation.id}"
        async_to_sync(channel_layer.group_send)(
            group,
            {
                "type": "message_status",
                "data": {"uazapi_message_id": uazapi_msg_id, "status": new_status},
            },
        )
    except Exception as e:
        logger.warning("WebSocket push falhou (message_status): %s", e)


def _push_conversation_update(conversation, account_id):
    from conversations.serializers import ConversationListSerializer
    try:
        group = f"account_{account_id}"
        async_to_sync(channel_layer.group_send)(
            group,
            {
                "type": "conversation_update",
                "data": ConversationListSerializer(conversation).data,
            },
        )
    except Exception as e:
        logger.warning("WebSocket push falhou (conversation_update): %s", e)