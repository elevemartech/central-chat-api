from django.contrib import admin
from .models import Message

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["conversation", "direction", "message_type", "status", "timestamp"]
    list_filter = ["direction", "message_type", "status"]
    search_fields = ["content", "uazapi_message_id"]