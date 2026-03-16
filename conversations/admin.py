from django.contrib import admin
from .models import Contact, Conversation


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ["phone", "name", "push_name", "created_at"]
    search_fields = ["phone", "name", "push_name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["account", "contact", "status", "unread_count", "last_message_at"]
    list_filter = ["status"]
    search_fields = ["contact__phone", "contact__name", "account__name"]
    readonly_fields = ["created_at", "updated_at"]