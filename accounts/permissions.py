from rest_framework.permissions import BasePermission
from .models import AccountUser


class IsAccountMember(BasePermission):
    """Permite acesso apenas a membros da conta."""

    def has_object_permission(self, request, view, obj):
        # obj pode ser Account ou ter account como FK
        account = obj if hasattr(obj, "uazapi_instance") else getattr(obj, "account", None)
        if account is None:
            return False
        return AccountUser.objects.filter(account=account, user=request.user).exists()


class IsAccountAdmin(BasePermission):
    """Permite apenas admins da conta."""

    def has_object_permission(self, request, view, obj):
        account = obj if hasattr(obj, "uazapi_instance") else getattr(obj, "account", None)
        if account is None:
            return False
        return AccountUser.objects.filter(
            account=account, user=request.user, role=AccountUser.Role.ADMIN
        ).exists()
