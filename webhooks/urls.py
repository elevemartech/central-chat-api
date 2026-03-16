from django.urls import path
from .views import UazapiWebhookView

urlpatterns = [
    path("webhook/uazapi/", UazapiWebhookView.as_view(), name="uazapi-webhook"),
    path("webhook/uazapi", UazapiWebhookView.as_view(), name="uazapi-webhook-noslash"),
]