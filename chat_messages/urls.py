from django.urls import path, include
from rest_framework_nested import routers
from rest_framework.routers import DefaultRouter
from conversations.views import ConversationViewSet
from .views import MessageViewSet

# /api/conversations/{conversation_pk}/messages/
# usando routers nested simples com path manual
urlpatterns = [
    path(
        "conversations/<uuid:conversation_pk>/messages/",
        MessageViewSet.as_view({"get": "list"}),
        name="conversation-messages",
    ),
    path(
        "conversations/<uuid:conversation_pk>/messages/send/",
        MessageViewSet.as_view({"post": "send"}),
        name="conversation-messages-send",
    ),
]
