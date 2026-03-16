import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from accounts.models import AccountUser


class ConversationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket por conversa.
    URL: ws://host/ws/conversations/{conversation_id}/
    """

    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.group_name = f"conversation_{self.conversation_id}"

        # Verifica se o usuário tem acesso à conversa
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close()
            return

        has_access = await self.check_access(user, self.conversation_id)
        if not has_access:
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        # O frontend pode enviar "typing" ou "mark_read"
        data = json.loads(text_data)
        event_type = data.get("type")

        if event_type == "typing":
            await self.channel_layer.group_send(
                self.group_name,
                {"type": "user_typing", "user": self.scope["user"].username},
            )

    # --- Handlers de eventos enviados pelo grupo ---

    async def new_message(self, event):
        """Recebe nova mensagem do Celery e envia para o WebSocket."""
        await self.send(text_data=json.dumps({"type": "new_message", "message": event["message"]}))

    async def message_status(self, event):
        """Atualização de status (sent/delivered/read)."""
        await self.send(text_data=json.dumps({"type": "message_status", "data": event["data"]}))

    async def user_typing(self, event):
        await self.send(text_data=json.dumps({"type": "typing", "user": event["user"]}))

    @database_sync_to_async
    def check_access(self, user, conversation_id):
        from conversations.models import Conversation
        try:
            conv = Conversation.objects.select_related("account").get(id=conversation_id)
            return AccountUser.objects.filter(account=conv.account, user=user).exists()
        except Conversation.DoesNotExist:
            return False


class AccountConsumer(AsyncWebsocketConsumer):
    """
    WebSocket por conta — recebe novas conversas e contagem de não lidos.
    URL: ws://host/ws/accounts/{account_id}/
    """

    async def connect(self):
        self.account_id = self.scope["url_route"]["kwargs"]["account_id"]
        self.group_name = f"account_{self.account_id}"

        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close()
            return

        has_access = await self.check_access(user, self.account_id)
        if not has_access:
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        pass

    async def conversation_update(self, event):
        """Atualiza lista de conversas no sidebar."""
        await self.send(text_data=json.dumps({"type": "conversation_update", "data": event["data"]}))

    @database_sync_to_async
    def check_access(self, user, account_id):
        return AccountUser.objects.filter(account_id=account_id, user=user).exists()
