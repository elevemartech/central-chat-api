from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from accounts.models import AccountUser
from conversations.models import Conversation
from .models import Message
from .serializers import MessageSerializer, SendMessageSerializer
from .tasks import send_outbound_message


class MessageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Listagem e detalhe de mensagens de uma conversa.
    Envio via POST /conversations/{id}/send/
    """
    serializer_class = MessageSerializer

    def get_queryset(self):
        user_accounts = AccountUser.objects.filter(user=self.request.user).values_list("account_id", flat=True)
        conversation_id = self.kwargs.get("conversation_pk") or self.request.query_params.get("conversation")
        qs = Message.objects.filter(conversation__account__in=user_accounts)
        if conversation_id:
            qs = qs.filter(conversation_id=conversation_id)
        return qs.order_by("timestamp")

    @action(detail=False, methods=["post"], url_path="send")
    def send(self, request, conversation_pk=None):
        """Envia mensagem para o WhatsApp via uazapi."""
        try:
            conversation = Conversation.objects.select_related("account", "contact").get(
                id=conversation_pk,
                account__members__user=request.user,
            )
        except Conversation.DoesNotExist:
            return Response({"detail": "Conversa não encontrada."}, status=status.HTTP_404_NOT_FOUND)

        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Enfileira o envio via Celery
        send_outbound_message.delay(
            conversation_id=str(conversation.id),
            message_type=serializer.validated_data["message_type"],
            content=serializer.validated_data.get("content", ""),
            quoted_message_id=serializer.validated_data.get("quoted_message_id", ""),
        )

        return Response({"detail": "Mensagem enfileirada para envio."}, status=status.HTTP_202_ACCEPTED)
