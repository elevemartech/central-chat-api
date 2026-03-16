from rest_framework import serializers
from .models import Contact, Conversation


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ["id", "phone", "name", "avatar_url", "push_name", "created_at"]
        read_only_fields = ["id", "created_at"]


class ConversationSerializer(serializers.ModelSerializer):
    contact = ContactSerializer(read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)
    account_color = serializers.CharField(source="account.color", read_only=True)

    class Meta:
        model = Conversation
        fields = [
            "id", "account", "account_name", "account_color",
            "contact", "status", "unread_count",
            "last_message_at", "last_message_preview",
            "created_at",
        ]
        read_only_fields = ["id", "unread_count", "last_message_at", "last_message_preview", "created_at"]


class ConversationListSerializer(serializers.ModelSerializer):
    """Versão leve para listagem."""
    contact_name = serializers.CharField(source="contact.name", read_only=True)
    contact_phone = serializers.CharField(source="contact.phone", read_only=True)
    contact_avatar = serializers.CharField(source="contact.avatar_url", read_only=True)

    class Meta:
        model = Conversation
        fields = [
            "id", "account", "contact_name", "contact_phone", "contact_avatar",
            "status", "unread_count", "last_message_at", "last_message_preview",
        ]
