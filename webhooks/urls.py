from django.urls import path
from .views import UazapiWebhookView

urlpatterns = [
    path("webhook/uazapi/<str:instance_id>/", UazapiWebhookView.as_view(), name="uazapi-webhook"),
]
