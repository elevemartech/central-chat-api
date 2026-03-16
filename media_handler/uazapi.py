"""
Funções para baixar mídia do uazapi usando POST /message/download.
A mídia fica disponível no storage do uazapi por apenas 2 dias.
Após esse prazo, é necessário chamar o endpoint novamente para reobter do CDN da Meta.
"""
import base64
import logging
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


def download_media(
    uazapi_message_id: str,
    account_uazapi_instance: str,
    account_uazapi_token: str,
    generate_mp3: bool = True,
    transcribe: bool = False,
    download_quoted: bool = False,
) -> dict:
    """
    Chama POST /message/download no uazapi.

    Retorna dict com:
        file_bytes  : bytes | None
        mime_type   : str
        file_url    : str   (URL temporária do uazapi, válida 2 dias)
        transcription: str
    """
    base_url = settings.UAZAPI_BASE_URL.rstrip("/")
    url = f"{base_url}/message/download/{account_uazapi_instance}"

    payload = {
        "id": uazapi_message_id,
        "return_base64": True,    # sempre pedimos base64 para salvar no Supabase
        "return_link": True,
        "generate_mp3": generate_mp3,
        "transcribe": transcribe,
        "download_quoted": download_quoted,
    }

    if transcribe and settings.OPENAI_API_KEY:
        payload["openai_apikey"] = settings.OPENAI_API_KEY

    try:
        response = httpx.post(
            url,
            json=payload,
            headers={"token": account_uazapi_token, "Content-Type": "application/json"},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as e:
        logger.error("Erro ao baixar mídia do uazapi [msg=%s]: %s", uazapi_message_id, e)
        raise

    file_bytes = None
    if data.get("base64Data"):
        file_bytes = base64.b64decode(data["base64Data"])

    return {
        "file_bytes": file_bytes,
        "mime_type": data.get("mimetype", "application/octet-stream"),
        "file_url": data.get("fileURL", ""),
        "transcription": data.get("transcription", ""),
    }


def detect_message_type(whatsapp_message: dict) -> str:
    """
    Detecta o tipo da mensagem com base no payload do uazapi (evento onmessage).
    """
    msg = whatsapp_message.get("message", {})
    if msg.get("conversation") or msg.get("extendedTextMessage"):
        return "text"
    if msg.get("imageMessage"):
        return "image"
    if msg.get("audioMessage") or msg.get("pttMessage"):
        return "audio"
    if msg.get("videoMessage"):
        return "video"
    if msg.get("documentMessage"):
        return "document"
    if msg.get("stickerMessage"):
        return "sticker"
    if msg.get("locationMessage"):
        return "location"
    if msg.get("contactMessage"):
        return "contact"
    return "text"


MEDIA_TYPES = {"image", "audio", "video", "document", "sticker"}


def is_media_message(message_type: str) -> bool:
    return message_type in MEDIA_TYPES
