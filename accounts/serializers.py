from rest_framework import serializers
from .models import Account, AccountUser


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = [
            "id", "name", "phone", "avatar_url", "color",
            "uazapi_instance", "is_connected", "created_at",
        ]
        read_only_fields = ["id", "is_connected", "created_at"]


class AccountCreateSerializer(serializers.ModelSerializer):
    """Inclui o token do uazapi apenas na criação."""
    class Meta:
        model = Account
        fields = [
            "id", "name", "phone", "avatar_url", "color",
            "uazapi_instance", "uazapi_token",
        ]
        read_only_fields = ["id"]


class AccountUserSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = AccountUser
        fields = ["id", "user", "username", "email", "role", "created_at"]
        read_only_fields = ["id", "created_at"]
