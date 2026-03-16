"""
Script de seed para popular o banco com dados de teste.

Como usar:
    poetry run python manage.py shell < seed.py

Ou no shell interativo:
    poetry run python manage.py shell
    >>> exec(open('seed.py').read())
"""

from django.contrib.auth.models import User
from django.utils.timezone import now
from datetime import timedelta
import random

from accounts.models import Account, AccountUser
from conversations.models import Contact, Conversation
from chat_messages.models import Message

print("🌱 Iniciando seed...")

# ─── Limpar dados anteriores (opcional) ──────────────────────────────────────
Message.objects.all().delete()
Conversation.objects.all().delete()
Contact.objects.all().delete()
Account.objects.all().delete()
User.objects.filter(is_superuser=False).delete()
print("🗑️  Dados anteriores removidos.")

# ─── Usuários ─────────────────────────────────────────────────────────────────
admin = User.objects.filter(username="admin").first()
if not admin:
    admin = User.objects.create_superuser("admin", "admin@example.com", "admin123")
    print("👤 Superuser 'admin' criado (senha: admin123)")
else:
    print("👤 Superuser 'admin' já existe, reutilizando.")

agente1 = User.objects.create_user("joao", "joao@example.com", "joao123", first_name="João")
agente2 = User.objects.create_user("maria", "maria@example.com", "maria123", first_name="Maria")
print("👥 Agentes criados: joao / maria (senha: joao123 / maria123)")

# ─── Contas (instâncias WhatsApp) ─────────────────────────────────────────────
conta_suporte = Account.objects.create(
    name="Suporte Técnico",
    phone="5511900000001",
    color="#3b82f6",
    uazapi_instance="instancia-suporte",
    uazapi_token="token-suporte-fake-123",
    is_connected=True,
)

conta_vendas = Account.objects.create(
    name="Vendas",
    phone="5521974221338",
    color="#10b981",
    uazapi_instance="instancia-vendas",
    uazapi_token="5c50ba9c-b3f9-4750-bcb5-dc73b2783c44",
    is_connected=True,
)
print("📱 Contas criadas: 'Suporte Técnico' e 'Vendas'")

# ─── Membros das contas ───────────────────────────────────────────────────────
AccountUser.objects.create(account=conta_suporte, user=admin,   role="admin")
AccountUser.objects.create(account=conta_suporte, user=agente1, role="agent")
AccountUser.objects.create(account=conta_vendas,  user=admin,   role="admin")
AccountUser.objects.create(account=conta_vendas,  user=agente2, role="agent")
print("🔗 Membros vinculados às contas.")

# ─── Contatos ─────────────────────────────────────────────────────────────────
contatos_data = [
    ("5511911111111", "Carlos Silva",    "carlos"),
    ("5511922222222", "Ana Souza",       "ana"),
    ("5511933333333", "Pedro Oliveira",  "pedro"),
    ("5511944444444", "Fernanda Costa",  "fernanda"),
    ("5511955555555", "Lucas Pereira",   "lucas"),
    ("5511966666666", "Juliana Martins", "juliana"),
    ("5521974021620", "Empresa XYZ",     "empresa_xyz"),
]

contatos = []
for phone, name, push in contatos_data:
    c = Contact.objects.create(phone=phone, name=name, push_name=push)
    contatos.append(c)
print(f"👤 {len(contatos)} contatos criados.")

# ─── Conversas e Mensagens ────────────────────────────────────────────────────
def criar_conversa(account, contact, msgs, status="open", unread=0):
    base_time = now() - timedelta(hours=random.randint(1, 72))

    last_ts = base_time
    preview = ""

    conv = Conversation.objects.create(
        account=account,
        contact=contact,
        status=status,
        unread_count=unread,
    )

    for i, (direction, content) in enumerate(msgs):
        ts = base_time + timedelta(minutes=i * random.randint(1, 10))
        Message.objects.create(
            conversation=conv,
            direction=direction,
            message_type="text",
            status="read" if direction == "inbound" else "delivered",
            content=content,
            timestamp=ts,
        )
        last_ts = ts
        preview = content

    conv.last_message_at = last_ts
    conv.last_message_preview = preview[:100]
    conv.save(update_fields=["last_message_at", "last_message_preview"])
    return conv


# Conversa 1 — Suporte com Carlos
criar_conversa(conta_suporte, contatos[0], [
    ("inbound",  "Olá, preciso de ajuda com meu pedido"),
    ("outbound", "Olá Carlos! Pode me passar o número do pedido?"),
    ("inbound",  "É o pedido #4521"),
    ("outbound", "Encontrei aqui! Seu pedido está em separação, deve sair hoje."),
    ("inbound",  "Ótimo! Obrigado pela atenção 😊"),
], unread=0)

# Conversa 2 — Suporte com Ana (não lida)
criar_conversa(conta_suporte, contatos[1], [
    ("inbound",  "Boa tarde! Meu produto chegou com defeito"),
    ("outbound", "Oi Ana, que situação! Pode me enviar uma foto do defeito?"),
    ("inbound",  "Claro, vou tirar agora"),
    ("inbound",  "Já enviei a foto pelo email"),
    ("inbound",  "Conseguiu ver?"),
], unread=2)

# Conversa 3 — Suporte com Pedro (resolvida)
criar_conversa(conta_suporte, contatos[2], [
    ("inbound",  "Quero cancelar meu pedido"),
    ("outbound", "Pedro, tudo bem? O pedido ainda pode ser cancelado. Confirma?"),
    ("inbound",  "Sim, pode cancelar"),
    ("outbound", "Cancelamento realizado! Estorno em até 5 dias úteis."),
    ("inbound",  "Perfeito, obrigado!"),
], status="resolved", unread=0)

# Conversa 4 — Vendas com Fernanda
criar_conversa(conta_vendas, contatos[3], [
    ("inbound",  "Vocês têm o plano anual com desconto?"),
    ("outbound", "Oi Fernanda! Sim, temos 20% de desconto no plano anual 🎉"),
    ("inbound",  "Que ótimo! Como faço para contratar?"),
    ("outbound", "Vou te enviar o link de pagamento agora mesmo!"),
], unread=0)

# Conversa 5 — Vendas com Lucas (não lida)
criar_conversa(conta_vendas, contatos[4], [
    ("inbound",  "Oi, vi o anúncio de vocês no Instagram"),
    ("inbound",  "Quero saber mais sobre o produto"),
    ("inbound",  "Têm versão trial?"),
], unread=3)

# Conversa 6 — Vendas com Juliana
criar_conversa(conta_vendas, contatos[5], [
    ("inbound",  "Olá! Sou revendedora, vocês trabalham com distribuição?"),
    ("outbound", "Oi Juliana! Sim temos programa de parceiros. Quer que eu te passe mais detalhes?"),
    ("inbound",  "Por favor!"),
    ("outbound", "Vou te adicionar no grupo de parceiros e compartilhar o material 📋"),
    ("inbound",  "Maravilha, aguardo!"),
], unread=0)

print("💬 6 conversas criadas com mensagens.")

# ─── Resumo ───────────────────────────────────────────────────────────────────
print("\n" + "="*50)
print("✅ Seed concluído com sucesso!")
print("="*50)
print(f"  Usuários  : {User.objects.count()} (admin / joao / maria)")
print(f"  Contas    : {Account.objects.count()} (Suporte / Vendas)")
print(f"  Contatos  : {Contact.objects.count()}")
print(f"  Conversas : {Conversation.objects.count()}")
print(f"  Mensagens : {Message.objects.count()}")
print("="*50)
print("\n🔑 Credenciais:")
print("  admin / admin123")
print("  joao  / joao123")
print("  maria / maria123")
print("\n🌐 Webhooks de teste:")
print(f"  POST /api/webhook/uazapi/instancia-suporte/?token=token-suporte-fake-123")
print(f"  POST /api/webhook/uazapi/instancia-vendas/?token=token-vendas-fake-456")