from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ContactViewSet, ConversationViewSet

router = DefaultRouter()
router.register("contacts", ContactViewSet, basename="contact")
router.register("conversations", ConversationViewSet, basename="conversation")

urlpatterns = [path("", include(router.urls))]
