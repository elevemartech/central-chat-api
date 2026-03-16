from django.contrib import admin
from accounts.models import Account, AccountUser

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "is_connected", "created_at"]
    search_fields = ["name", "phone"]

@admin.register(AccountUser)
class AccountUserAdmin(admin.ModelAdmin):
    list_display = ["user", "account", "role", "created_at"]