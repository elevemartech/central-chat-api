import logging
import mimetypes
import uuid
from django.conf import settings
import httpx

logger = logging.getLogger(__name__)

SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_KEY = settings.SUPABASE_SERVICE_KEY
BUCKET = settings.SUPABASE_BUCKET


def upload_bytes_to_supabase(raw_bytes: bytes, filename: str, mime_type: str, account_id: str) -> str:
    """
    Faz upload de bytes para o Supabase Storage.
    Retorna a URL pública do arquivo.
    Path: {account_id}/{filename}
    """
    # Garante nome único
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    unique_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    path = f"{account_id}/{unique_name}"

    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}"

    try:
        response = httpx.put(
            url,
            content=raw_bytes,
            headers={
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": mime_type,
                "x-upsert": "true",
            },
            timeout=60,
        )
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.error("Supabase upload falhou: %s", e)
        raise

    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}"
    logger.info("Mídia salva: %s", public_url)
    return public_url


def delete_from_supabase(public_url: str):
    """Remove um arquivo do Supabase Storage pelo URL público."""
    # Extrai o path do URL
    prefix = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/"
    if not public_url.startswith(prefix):
        return
    path = public_url[len(prefix):]

    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}"
    try:
        httpx.delete(
            url,
            headers={"Authorization": f"Bearer {SUPABASE_KEY}"},
            timeout=15,
        )
    except httpx.HTTPError as e:
        logger.warning("Falha ao deletar do Supabase: %s", e)
