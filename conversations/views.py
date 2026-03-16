from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from accounts.models import AccountUser
from .models import Contact, Conversation
from .serializers import ContactSerializer, ConversationSerializer, ConversationListSerializer


class ContactViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ContactSerializer

    def get_queryset(self):
        # Retorna contatos das contas do usuário
        user_accounts = AccountUser.objects.filter(user=self.request.user).values_list("account_id", flat=True)
        return Contact.objects.filter(conversations__account__in=user_accounts).distinct()


class ConversationViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["account", "status"]

    def get_queryset(self):
        user_accounts = AccountUser.objects.filter(user=self.request.user).values_list("account_id", flat=True)
        return (
            Conversation.objects.filter(account__in=user_accounts)
            .select_related("contact", "account")
            .order_by("-last_message_at")
        )

    def get_serializer_class(self):
        if self.action == "list":
            return ConversationListSerializer
        return ConversationSerializer

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        conversation = self.get_object()
        conversation.unread_count = 0
        conversation.save(update_fields=["unread_count"])
        return Response({"unread_count": 0})

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        conversation = self.get_object()
        conversation.status = Conversation.Status.RESOLVED
        conversation.save(update_fields=["status"])
        return Response({"status": conversation.status})
