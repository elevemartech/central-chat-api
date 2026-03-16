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
    event = payload.get("event") or payload.get("type", "")

    # LOG TEMPORÁRIO — mostra o payload completo para debug
    logger.info("=== PAYLOAD RECEBIDO ===")
    logger.info("event: %s", event)
    logger.info("payload keys: %s", list(payload.keys()))
    logger.info("payload completo: %s", payload)
    logger.info("========================")

    try:
        if event == "onmessage":
            handle_incoming_message(account_id, payload)
        elif event == "onack":
            handle_ack(payload)
        elif event in ("onconnected", "ondisconnected"):
            handle_connection_status(account_id, event)
        else:
            logger.warning("Evento ignorado (não mapeado): '%s'", event)
    except Exception as exc:
        logger.exception("Erro ao processar evento %s da conta %s", event, account_id)
        raise self.retry(exc=exc)


# ─── Handlers ────────────────────────────────────────────────────────────────

def handle_incoming_message(account_id: str, payload: dict):
    from accounts.models import Account
    from conversations.models import Contact, Conversation
    from chat_messages.models import Message
    from media_handler.uazapi import detect_message_type, is_media_message, download_media
    from media_handler.supabase import upload_bytes_to_supabase

    data = payload.get("data", payload)
    key = data.get("key", {})

    if key.get("fromMe"):
        return

    raw_jid = key.get("remoteJid", "")
    phone = raw_jid.replace("@s.whatsapp.net", "").replace("@g.us", "")
    if not phone:
        logger.warning("JID inválido: %s", raw_jid)
        return

    uazapi_msg_id = key.get("id", "")

    if Message.objects.filter(uazapi_message_id=uazapi_msg_id).exists():
        logger.debug("Mensagem já processada: %s", uazapi_msg_id)
        return

    account = Account.objects.get(id=account_id)
    push_name = data.get("pushName", "")

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
        logger.info("Novo contato cadastrado automaticamente: %s (%s)", phone, push_name)

    conversation, conv_created = Conversation.objects.get_or_create(
        account=account,
        contact=contact,
    )
    if conv_created:
        logger.info("Nova conversa criada: conta=%s contato=%s", account.uazapi_instance, phone)

    message_type = detect_message_type(data)

    msg_body = data.get("message", {})
    text_content = (
        msg_body.get("conversation")
        or msg_body.get("extendedTextMessage", {}).get("text", "")
        or ""
    )

    media_url = ""
    media_mime = ""
    media_filename = ""
    media_size = None
    audio_transcription = ""

    if is_media_message(message_type) and uazapi_msg_id:
        try:
            result = download_media(
                uazapi_message_id=uazapi_msg_id,
                account_uazapi_instance=account.uazapi_instance,
                account_uazapi_token=account.uazapi_token,
                generate_mp3=(message_type == "audio"),
                transcribe=False,
            )

            if result["file_bytes"]:
                ext_map = {
                    "image": "jpg", "audio": "mp3", "video": "mp4",
                    "document": "bin", "sticker": "webp",
                }
                filename = f"{uazapi_msg_id}.{ext_map.get(message_type, 'bin')}"
                media_url = upload_bytes_to_supabase(
                    raw_bytes=result["file_bytes"],
                    filename=filename,
                    mime_type=result["mime_type"],
                    account_id=str(account_id),
                )
                media_mime = result["mime_type"]
                media_filename = filename
                media_size = len(result["file_bytes"])
                audio_transcription = result.get("transcription", "")
            else:
                media_url = result["file_url"]
                media_mime = result["mime_type"]

        except Exception as e:
            logger.error("Falha ao baixar/armazenar mídia [%s]: %s", uazapi_msg_id, e)

    location_data = msg_body.get("locationMessage", {})

    ts_raw = data.get("messageTimestamp") or data.get("timestamp")
    timestamp = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc) if ts_raw else now()

    message = Message.objects.create(
        conversation=conversation,
        uazapi_message_id=uazapi_msg_id,
        direction="inbound",
        message_type=message_type,
        status="delivered",
        content=text_content,
        media_url=media_url,
        media_mime=media_mime,
        media_filename=media_filename,
        media_size=media_size,
        audio_transcription=audio_transcription,
        location_lat=location_data.get("degreesLatitude"),
        location_lng=location_data.get("degreesLongitude"),
        location_name=location_data.get("name", ""),
        timestamp=timestamp,
    )

    preview = text_content[:100] if text_content else f"[{message_type}]"
    Conversation.objects.filter(id=conversation.id).update(
        last_message_at=timestamp,
        last_message_preview=preview,
        unread_count=conversation.unread_count + 1,
    )

    _push_new_message(conversation, message)
    _push_conversation_update(conversation, account_id)


def handle_ack(payload: dict):
    from chat_messages.models import Message

    data = payload.get("data", payload)
    uazapi_msg_id = data.get("id") or data.get("key", {}).get("id", "")
    ack_value = data.get("ack")

    status_map = {1: "sent", 2: "delivered", 3: "read", -1: "failed"}
    new_status = status_map.get(ack_value)

    if not new_status or not uazapi_msg_id:
        return

    updated = Message.objects.filter(uazapi_message_id=uazapi_msg_id).update(status=new_status)
    if updated:
        try:
            msg = Message.objects.select_related("conversation").get(uazapi_message_id=uazapi_msg_id)
            _push_message_status(msg.conversation, uazapi_msg_id, new_status)
        except Message.DoesNotExist:
            pass


def handle_connection_status(account_id: str, event: str):
    from accounts.models import Account
    is_connected = event == "onconnected"
    Account.objects.filter(id=account_id).update(is_connected=is_connected)
    logger.info("Conta %s %s", account_id, "conectada" if is_connected else "desconectada")


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