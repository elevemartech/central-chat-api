from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),

    # Auth
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Apps
    path("api/", include("accounts.urls")),
    path("api/", include("conversations.urls")),
    path("api/", include("chat_messages.urls")),
    path("api/", include("webhooks.urls")),
]
