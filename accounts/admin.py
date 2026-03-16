from django.contrib import admin
from .models import Account, AccountUser


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "uazapi_instance", "is_connected", "created_at"]
    search_fields = ["name", "phone", "uazapi_instance"]
    list_filter = ["is_connected"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(AccountUser)
class AccountUserAdmin(admin.ModelAdmin):
    list_display = ["user", "account", "role", "created_at"]
    list_filter = ["role"]
    search_fields = ["user__username", "account__name"]