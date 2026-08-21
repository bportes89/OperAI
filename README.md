# OperAI

SaaS de agentes de IA para PME (BYOK). Stack local e deploy sem VPS: **Vercel + Neon + Railway/Render**.

## Deploy sem VPS (3 clientes de teste)

### 1. Neon (Postgres)
1. Crie projeto em https://neon.tech  
2. Copie a connection string (`postgresql://...`)  
3. Guarde para `OPERAI_DATABASE_URL`

### 2. Railway ou Render (API)
**Railway (recomendado):**
1. New Project → Deploy from GitHub (pasta `backend`)  
2. Root directory: `operai/backend` (ou o path do repo)  
3. Usa o `Dockerfile` + `scripts/start.sh` (roda `alembic upgrade head` e sobe a API)  
4. Variáveis:

```
OPERAI_DATABASE_URL=<cole a URL do Neon>
OPERAI_JWT_SECRET=<string longa aleatória 40+ chars>
OPERAI_ENCRYPTION_KEY=<outra string longa>
OPERAI_CORS_ORIGINS=["https://SEU-APP.vercel.app"]
OPERAI_FRONTEND_URL=https://SEU-APP.vercel.app
OPERAI_PUBLIC_API_URL=https://SUA-API.up.railway.app
OPERAI_ASAAS_API_URL=https://sandbox.asaas.com/api/v3
OPERAI_ASAAS_API_KEY=
OPERAI_ASAAS_WEBHOOK_TOKEN=<token seu>
OPERAI_TRIAL_DAYS=14
```

5. Confirme health: `GET /api/v1/health`

**Render:** use o `render.yaml` na pasta `backend` e as mesmas envs.

### 3. Vercel (frontend)
1. Import repo → root `operai/frontend`  
2. Framework: Next.js  
3. Env:

```
NEXT_PUBLIC_API_URL=https://SUA-API.up.railway.app
```

4. Deploy → anote a URL `https://xxx.vercel.app`  
5. Volte na Railway e ajuste `OPERAI_CORS_ORIGINS` + `OPERAI_FRONTEND_URL` com essa URL; redeploy da API.

### 4. Teste
1. Abra a URL da Vercel  
2. Cadastre uma empresa (trial 14 dias)  
3. Em Conta/Billing use confirm-local se Asaas estiver vazio  
4. Cole chave Groq/OpenAI em Configurações → LLM  
5. WhatsApp real fica para depois (precisa VPS + Evolution)

## Local

```bash
# Backend
cd backend && uvicorn app.main:app --reload --host 127.0.0.1 --port 8001

# Frontend
cd frontend && npm run dev
```

## Planos
Start R$197 · Pro R$397 · Business R$797 · BYOK (LLM do cliente)
