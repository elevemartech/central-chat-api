import uuid
from django.db import models
from accounts.models import Account


class Contact(models.Model):
    """Contato externo — o cliente no WhatsApp."""
    phone = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=120, blank=True)
    avatar_url = models.URLField(blank=True)
    push_name = models.CharField(max_length=120, blank=True)  # nome no WhatsApp
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name or self.phone


class Conversation(models.Model):
    """Chat entre uma conta (host) e um contato."""

    class Status(models.TextChoices):
        OPEN = "open", "Aberta"
        RESOLVED = "resolved", "Resolvida"
        ARCHIVED = "archived", "Arquivada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="conversations")
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="conversations")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    unread_count = models.PositiveIntegerField(default=0)
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_message_preview = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("account", "contact")
        ordering = ["-last_message_at"]

    def __str__(self):
        return f"{self.account.name} ↔ {self.contact}"
