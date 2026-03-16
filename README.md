# Chat Central — API

Backend centralizado para gerenciar múltiplas contas WhatsApp via [uazapi](https://uazapi.com), com Django REST Framework, Supabase e WebSocket em tempo real.

## Stack

| Camada | Tecnologia |
|--------|-----------|
| API REST | Django 5 + DRF |
| Autenticação | JWT (SimpleJWT) |
| Banco | Supabase (PostgreSQL) |
| Storage de mídia | Supabase Storage |
| Fila de tarefas | Celery + Redis |
| WebSocket | Django Channels + Redis |
| WhatsApp | uazapi |

## Estrutura

```
chat-central/
├── config/               # Settings, URLs, Celery, ASGI
├── accounts/             # Contas uazapi e usuários
├── conversations/        # Conversas, contatos, WebSocket consumers
├── messages/             # Mensagens (texto, imagem, áudio, vídeo, doc)
├── webhooks/             # Endpoint e tasks do uazapi
└── media_handler/        # Download do uazapi + upload Supabase
```

## Setup local

### 1. Clonar e configurar ambiente

```bash
git clone <seu-repo>
cd chat-central
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Variáveis de ambiente

```bash
cp .env.example .env
# Edite .env com suas credenciais
```

### 3. Supabase

1. Crie um projeto em [supabase.com](https://supabase.com)
2. Copie a **Connection String** em Settings → Database
3. Crie o bucket `chat-media` em Storage → New bucket (Public read)
4. Cole as credenciais no `.env`

### 4. Redis local

```bash
# macOS
brew install redis && brew services start redis

# Ubuntu/Debian
sudo apt install redis-server && sudo systemctl start redis

# Docker
docker run -d -p 6379:6379 redis:alpine
```

### 5. Migrations e servidor

```bash
python manage.py migrate
python manage.py createsuperuser

# Terminal 1 — Django (ASGI para WebSocket)
daphne -p 8000 config.asgi:application

# Terminal 2 — Celery worker
celery -A config worker -l info

# Terminal 3 — Celery beat (tarefas agendadas, opcional)
celery -A config beat -l info
```

### 6. Configurar webhook no uazapi

No painel do uazapi, configure o webhook da instância para:

```
POST https://seu-dominio.com/api/webhook/uazapi/{instance_id}/?token={uazapi_token}
```

> Em desenvolvimento, use [ngrok](https://ngrok.com) para expor o localhost:
> ```bash
> ngrok http 8000
> ```

## Endpoints principais

### Autenticação
```
POST /api/auth/token/         → Login (retorna access + refresh)
POST /api/auth/refresh/       → Renova access token
```

### Contas (hosts)
```
GET    /api/accounts/                    → Lista contas do usuário
POST   /api/accounts/                    → Cria nova conta
GET    /api/accounts/{id}/               → Detalhe
PATCH  /api/accounts/{id}/               → Atualiza
GET    /api/accounts/{id}/members/       → Lista membros
POST   /api/accounts/{id}/members/       → Adiciona membro
DELETE /api/accounts/{id}/members/       → Remove membro
```

### Conversas
```
GET   /api/conversations/                → Lista conversas (filtra por ?account={id}&status=open)
GET   /api/conversations/{id}/           → Detalhe
POST  /api/conversations/{id}/mark_read/ → Zera não lidos
POST  /api/conversations/{id}/resolve/   → Resolve conversa
```

### Mensagens
```
GET  /api/conversations/{id}/messages/       → Histórico (paginado)
POST /api/conversations/{id}/messages/send/  → Envia mensagem
```

### Contatos
```
GET /api/contacts/   → Lista contatos
```

### Webhook
```
POST /api/webhook/uazapi/{instance_id}/?token={token}  → Recebe eventos do uazapi
```

## WebSocket

```
ws://host/ws/conversations/{conversation_id}/   → Push de mensagens em tempo real
ws://host/ws/accounts/{account_id}/            → Atualizações de conversas
```

**Eventos recebidos pelo frontend:**
```json
{ "type": "new_message",         "message": { ...MessageSerializer } }
{ "type": "message_status",      "data": { "uazapi_message_id": "...", "status": "read" } }
{ "type": "conversation_update", "data": { ...ConversationListSerializer } }
{ "type": "typing",              "user": "username" }
```

## Fluxo de mídia (uazapi → Supabase)

```
uazapi envia evento onmessage
    └── webhook recebe e enfileira task Celery
         └── task chama POST /message/download no uazapi
              └── obtém bytes da mídia
                   └── faz upload no Supabase Storage (bucket chat-media)
                        └── salva Message com media_url permanente
                             └── push via WebSocket para o frontend
```

> **Atenção:** O uazapi mantém a mídia por apenas 2 dias. Por isso, fazemos o download imediato e armazenamos permanentemente no Supabase Storage.

## Deploy

### Railway / Render

**Procfile:**
```
web: daphne -b 0.0.0.0 -p $PORT config.asgi:application
worker: celery -A config worker -l info --concurrency=2
```

Configure todas as variáveis do `.env.example` no painel da plataforma.

## Licença

MIT
# central-chat-api
