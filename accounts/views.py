from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Account, AccountUser
from .serializers import AccountSerializer, AccountCreateSerializer, AccountUserSerializer
from .permissions import IsAccountAdmin


class AccountViewSet(viewsets.ModelViewSet):
    """CRUD de contas. Cada usuário vê apenas suas contas."""

    def get_queryset(self):
        return Account.objects.filter(members__user=self.request.user)

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return AccountCreateSerializer
        return AccountSerializer

    def perform_create(self, serializer):
        account = serializer.save()
        # Criador vira admin automaticamente
        AccountUser.objects.create(
            account=account, user=self.request.user, role=AccountUser.Role.ADMIN
        )

    @action(detail=True, methods=["get", "post", "delete"], url_path="members")
    def members(self, request, pk=None):
        account = self.get_object()
        if request.method == "GET":
            members = AccountUser.objects.filter(account=account)
            return Response(AccountUserSerializer(members, many=True).data)
        if request.method == "POST":
            data = {**request.data, "account": account.id}
            serializer = AccountUserSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save(account=account)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        if request.method == "DELETE":
            user_id = request.data.get("user_id")
            AccountUser.objects.filter(account=account, user_id=user_id).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
