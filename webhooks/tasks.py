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

    logger.info(
        "Evento recebido: EventType=%s instance=%s",
        event_type,
        payload.get("instanceName", ""),
    )

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

    from_me = message.get("fromMe", False)

    # Mensagens da API não disparam webhook (configurado no uazapi).
    # Portanto, todo fromMe=True que chegar aqui foi enviado pelo celular do dono
    # fora da plataforma — deve ser salvo para manter histórico completo.

    # ── Extrai telefone do contato ───────────────────────────────────────────
    # Em grupos: chatid é o ID do grupo (@g.us), então usamos sender_pn
    # Em 1-a-1:  chatid é sempre o número do contato, independente de fromMe
    #            (sender_pn pode ser o dono quando ele responde pelo celular)
    is_group = message.get("isGroup", False)

    if is_group:
        raw_phone = message.get("sender_pn", "")
    else:
        raw_phone = message.get("chatid", "")

    phone = raw_phone.replace("@s.whatsapp.net", "").replace("@g.us", "")

    if not phone:
        logger.warning("Telefone não encontrado no payload")
        return

    # ── Idempotência ─────────────────────────────────────────────────────────
    uazapi_msg_id = message.get("messageid", "") or message.get("id", "")

    if uazapi_msg_id and Message.objects.filter(uazapi_message_id=uazapi_msg_id).exists():
        logger.debug("Mensagem já processada: %s", uazapi_msg_id)
        return

    account = Account.objects.get(id=account_id)

    # ── Nome do contato ──────────────────────────────────────────────────────
    push_name = (
        chat.get("wa_name")
        or chat.get("wa_contactName")
        or chat.get("name")
        or message.get("senderName")
        or ""
    )

    # ── Avatar do contato (foto do WhatsApp) ─────────────────────────────────
    avatar_url = chat.get("imagePreview", "")

    # ── Cadastro automático do contato ───────────────────────────────────────
    contact, created = Contact.objects.get_or_create(
        phone=phone,
        defaults={"name": push_name, "push_name": push_name, "avatar_url": avatar_url},
    )
    if not created:
        updated_fields = []
        if push_name:
            if not contact.name:
                contact.name = push_name
                updated_fields.append("name")
            if contact.push_name != push_name:
                contact.push_name = push_name
                updated_fields.append("push_name")
        if avatar_url and contact.avatar_url != avatar_url:
            contact.avatar_url = avatar_url
            updated_fields.append("avatar_url")
        if updated_fields:
            contact.save(update_fields=updated_fields)

    if created:
        logger.info("Novo contato cadastrado: %s (%s)", phone, push_name)

    # ── Cadastro automático da conversa ──────────────────────────────────────
    conversation, conv_created = Conversation.objects.get_or_create(
        account=account,
        contact=contact,
    )
    if conv_created:
        logger.info(
            "Nova conversa criada: conta=%s contato=%s",
            account.uazapi_instance,
            phone,
        )

    # ── Tipo da mensagem ─────────────────────────────────────────────────────
    raw_type = message.get("messageType", "") or message.get("type", "text")
    type_map = {
        # Tipos vindos de messageType
        "Conversation": "text",
        "ExtendedTextMessage": "text",
        "ImageMessage": "image",
        "AudioMessage": "audio",
        "VideoMessage": "video",
        "DocumentMessage": "document",
        "StickerMessage": "sticker",
        "LocationMessage": "location",
        "ContactMessage": "contact",
        # Tipos vindos de type (fallback)
        "text": "text",
        "media": "audio",  # mediaType PTT/audio chega com type="media"
        "image": "image",
        "video": "video",
        "document": "document",
        "sticker": "sticker",
        "location": "location",
        "contact": "contact",
    }
    message_type = type_map.get(raw_type, "text")

    # Refinamento: se type="media", usar mediaType para distinguir áudio de imagem etc.
    if raw_type == "media":
        media_type_raw = message.get("mediaType", "").lower()
        media_remap = {
            "ptt": "audio",
            "audio": "audio",
            "image": "image",
            "video": "video",
            "document": "document",
            "sticker": "sticker",
        }
        message_type = media_remap.get(media_type_raw, "audio")

    # ── Conteúdo de texto ────────────────────────────────────────────────────
    text_content = message.get("text", "") or ""

    # ── Campos de mídia extraídos do content (quando é objeto) ───────────────
    audio_duration = None
    media_mime = ""

    content_field = message.get("content")
    if isinstance(content_field, dict):
        media_mime = content_field.get("mimetype", "")
        if message_type == "audio":
            audio_duration = content_field.get("seconds")

    # ── Timestamp ────────────────────────────────────────────────────────────
    ts_raw = message.get("messageTimestamp")
    if ts_raw:
        # uazapi envia em milissegundos quando > 1e10
        ts_seconds = int(ts_raw) / 1000 if int(ts_raw) > 1e10 else int(ts_raw)
        timestamp = datetime.fromtimestamp(ts_seconds, tz=timezone.utc)
    else:
        timestamp = now()

    # ── Persiste a mensagem ──────────────────────────────────────────────────
    direction = "outbound" if from_me else "inbound"
    msg_status = "sent" if from_me else "delivered"

    create_kwargs = dict(
        conversation=conversation,
        uazapi_message_id=uazapi_msg_id,
        direction=direction,
        message_type=message_type,
        status=msg_status,
        content=text_content,
        timestamp=timestamp,
    )
    if media_mime:
        create_kwargs["media_mime"] = media_mime
    if audio_duration is not None:
        create_kwargs["audio_duration_seconds"] = audio_duration

    msg_obj = Message.objects.create(**create_kwargs)
    logger.info(
        "Mensagem salva: %s | type=%s | '%s'",
        phone,
        message_type,
        text_content[:50] or f"[{message_type}]",
    )

    # ── Atualiza conversa ────────────────────────────────────────────────────
    # Mensagens do próprio dono não incrementam o contador de não lidos
    preview = text_content[:100] if text_content else f"[{message_type}]"
    update_fields = dict(
        last_message_at=timestamp,
        last_message_preview=preview,
    )
    if not from_me:
        update_fields["unread_count"] = conversation.unread_count + 1

    Conversation.objects.filter(id=conversation.id).update(**update_fields)

    # ── Push via WebSocket ───────────────────────────────────────────────────
    _push_new_message(conversation, msg_obj)
    _push_conversation_update(conversation, account_id)


def handle_connection_status(account_id: str, status: str):
    from accounts.models import Account

    is_connected = status in ("open", "connected", "onconnected")
    Account.objects.filter(id=account_id).update(is_connected=is_connected)
    logger.info("Conta %s status: %s (connected=%s)", account_id, status, is_connected)


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