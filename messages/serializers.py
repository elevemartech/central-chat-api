from rest_framework import serializers
from .models import Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "id", "conversation", "uazapi_message_id",
            "direction", "message_type", "status",
            "content",
            "media_url", "media_mime", "media_filename", "media_size",
            "audio_transcription", "audio_duration_seconds",
            "location_lat", "location_lng", "location_name",
            "quoted_message_id", "quoted_content", "quoted_media_url",
            "timestamp", "created_at",
        ]
        read_only_fields = [
            "id", "uazapi_message_id", "direction", "message_type",
            "media_url", "media_mime", "media_filename", "media_size",
            "audio_transcription", "created_at",
        ]


class SendMessageSerializer(serializers.Serializer):
    """Validação para envio de mensagem pelo agente."""
    message_type = serializers.ChoiceField(choices=Message.MessageType.choices, default=Message.MessageType.TEXT)
    content = serializers.CharField(required=False, allow_blank=True)
    media_file = serializers.FileField(required=False)
    quoted_message_id = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        if data.get("message_type") == Message.MessageType.TEXT and not data.get("content"):
            raise serializers.ValidationError("content é obrigatório para mensagens de texto.")
        if data.get("message_type") != Message.MessageType.TEXT and not data.get("media_file"):
            raise serializers.ValidationError("media_file é obrigatório para mensagens de mídia.")
        return data
