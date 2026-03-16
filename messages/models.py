import uuid
from django.db import models
from conversations.models import Conversation


class Message(models.Model):

    class MessageType(models.TextChoices):
        TEXT = "text", "Texto"
        IMAGE = "image", "Imagem"
        AUDIO = "audio", "Áudio"
        VIDEO = "video", "Vídeo"
        DOCUMENT = "document", "Documento"
        STICKER = "sticker", "Sticker"
        LOCATION = "location", "Localização"
        CONTACT = "contact", "Contato"

    class Direction(models.TextChoices):
        INBOUND = "inbound", "Recebida"
        OUTBOUND = "outbound", "Enviada"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        SENT = "sent", "Enviada"
        DELIVERED = "delivered", "Entregue"
        READ = "read", "Lida"
        FAILED = "failed", "Falhou"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")

    # ID da mensagem no uazapi/WhatsApp
    uazapi_message_id = models.CharField(max_length=120, unique=True, null=True, blank=True)

    direction = models.CharField(max_length=10, choices=Direction.choices)
    message_type = models.CharField(max_length=20, choices=MessageType.choices, default=MessageType.TEXT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SENT)

    # Conteúdo de texto
    content = models.TextField(blank=True)

    # Mídia — armazenada no Supabase Storage
    media_url = models.URLField(blank=True, max_length=1000)
    media_mime = models.CharField(max_length=80, blank=True)
    media_filename = models.CharField(max_length=255, blank=True)
    media_size = models.PositiveBigIntegerField(null=True, blank=True)

    # Áudio específico
    audio_transcription = models.TextField(blank=True)
    audio_duration_seconds = models.PositiveIntegerField(null=True, blank=True)

    # Localização
    location_lat = models.FloatField(null=True, blank=True)
    location_lng = models.FloatField(null=True, blank=True)
    location_name = models.CharField(max_length=255, blank=True)

    # Mensagem citada (reply)
    quoted_message_id = models.CharField(max_length=120, blank=True)
    quoted_content = models.TextField(blank=True)
    quoted_media_url = models.URLField(blank=True, max_length=1000)

    # Horário real da mensagem no WhatsApp
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"[{self.direction}] {self.message_type} — {self.conversation}"
