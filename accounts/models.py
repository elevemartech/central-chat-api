import uuid
from django.db import models
from django.contrib.auth.models import User


class Account(models.Model):
    """
    Uma conta = uma instância/número WhatsApp no uazapi.
    Equivale ao 'Host' no frontend.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, unique=True, blank=True)
    avatar_url = models.URLField(blank=True)
    color = models.CharField(max_length=7, default="#3b82f6")

    # Credenciais uazapi
    uazapi_instance = models.CharField(max_length=120, unique=True)
    uazapi_token = models.CharField(max_length=255)

    is_connected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.phone})"


class AccountUser(models.Model):
    """Vínculo entre usuários do sistema e contas WhatsApp."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        AGENT = "agent", "Agente"

    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="account_memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.AGENT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("account", "user")

    def __str__(self):
        return f"{self.user.username} → {self.account.name} ({self.role})"
