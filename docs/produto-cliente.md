# OperAI — Documentação do produto

**OperAI** é um SaaS de agentes de IA para PMEs. A empresa traz a própria chave de LLM (**BYOK**), e a plataforma entrega atendimento (WhatsApp), cobrança, vendas e marketing com o **conhecimento da própria empresa**.

Site: https://oper-ai-brown.vercel.app  
API: https://operai-x64r.onrender.com  

---

## 1. O que foi construído

### 1.1 Plataforma SaaS
- Landing com planos e trial
- Cadastro de empresa (multi-tenant) + login
- Trial de **14 dias** no plano Start
- Assinatura mensal (Asaas sandbox hoje; produção quando a chave live estiver configurada)
- Onboarding guiado (conta → LLM → FAQ → WhatsApp)
- Controle de acesso por papéis: `owner`, `admin`, `manager`, `operator`, `viewer`

### 1.2 Núcleo operacional
| Módulo | O que faz |
|--------|-----------|
| **Visão geral** | Dashboard com indicadores e atividade recente |
| **Agentes** | Comercial, Atendimento (WhatsApp), Cobrança e Marketing — criar, ativar e testar em chat |
| **Conhecimento** | Base FAQ/documentos da empresa; busca e uso nas respostas dos agentes (RAG) |
| **WhatsApp** | Inbox de conversas; conexão Evolution (local/simulada sem VPS; real com Evolution hospedada) |
| **CRM** | Oportunidades (pipeline de vendas) |
| **Cobrança** | Contas a receber, resumo e baixa de pagamentos |
| **Marketing** | Campanhas e status (planejamento operacional) |
| **Equipe** | Convidar/criar membros e definir papéis |
| **Chave LLM** | Configurar OpenAI, Groq ou OpenRouter (chave criptografada) |
| **Conta / Billing** | Status do trial/assinatura e contratação de plano |

### 1.3 Infraestrutura (sem VPS de aplicação)
| Camada | Serviço |
|--------|---------|
| Frontend | Vercel (Next.js) |
| API | Render (Docker + FastAPI) |
| Banco | Neon (Postgres) |

WhatsApp **real 24/7** fica fora desse stack: exige Evolution API em infra própria (ex.: VPS) quando o cliente quiser canal oficial.

---

## 2. Diferenciais para o cliente

### 2.1 BYOK — custo previsível de IA
O cliente usa **a própria chave** de OpenAI, Groq ou OpenRouter.  
A mensalidade da OperAI cobre a plataforma; o gasto de tokens fica com o cliente. Isso evita surpresa na fatura de IA e dá liberdade de provedor/modelo.

### 2.2 Agentes no contexto da empresa
As respostas usam a **base de conhecimento** (FAQ, políticas, scripts).  
Não é um chatbot genérico: o agente fala com o vocabulário e as regras do negócio.

### 2.3 Operação unificada
Em um só lugar:
- Atendimento (WhatsApp)
- Vendas (CRM + agente comercial)
- Cobrança (títulos + agente financeiro)
- Marketing (campanhas)
- Equipe e papéis

### 2.4 Multi-empresa desde o dia 1
Cada cliente tem **organização + identificador (slug)** próprio. Dados isolados. Login com e-mail, senha e identificador da empresa.

### 2.5 Time-to-value rápido
1. Criar conta (trial 14 dias)  
2. Colar chave LLM  
3. Subir FAQ  
4. Conectar WhatsApp (quando Evolution estiver disponível)  
5. Ativar agentes  

### 2.6 Planos claros
| Plano | Preço | Foco |
|-------|-------|------|
| **Start** | R$ 197/mês | Entrada (1 agente, time pequeno) |
| **Pro** | R$ 397/mês | 4 agentes + CRM + cobrança + campanhas |
| **Business** | R$ 797/mês | Escala (mais agentes e usuários) |

---

## 3. Como o cliente utiliza o sistema

### 3.1 Primeiro acesso
1. Acesse o site → **Começar trial** / **Criar conta**
2. Informe: nome, e-mail, senha, nome da empresa e **identificador** (ex.: `minha-loja`)
3. Guarde o identificador — ele entra no login junto com e-mail e senha
4. Faça login em **Entrar**

> Em produção não há usuário demo pré-criado. Cada empresa se cadastra.

### 3.2 Onboarding recomendado
No menu **Onboarding**:
1. **Conta e trial** — conferir período de teste  
2. **Chave LLM** — Configurações → Chave LLM (Groq costuma ser rápido para testes)  
3. **FAQ / Conhecimento** — cadastrar textos: horário, políticas, prazos, preços, scripts  
4. **WhatsApp** — conectar canal (Evolution quando houver; modo local para demonstração)

### 3.3 Fluxo do dia a dia

**Atendimento**
1. Ative o agente **Atendimento**
2. Em **WhatsApp**, acompanhe as threads
3. Com Evolution real: mensagens entram e o agente pode responder com base no conhecimento
4. Sem Evolution: use o chat de teste em **Agentes** para validar respostas

**Vendas**
1. Cadastre oportunidades no **CRM**
2. Use o agente **Comercial** para treinar respostas de proposta/qualificação

**Cobrança**
1. Lance títulos em **Cobrança**
2. Acompanhe em aberto / atraso / recebido
3. Use o agente **Cobrança** para scripts de follow-up

**Marketing**
1. Crie campanhas em **Marketing**
2. Avance status conforme o fluxo da equipe

**Equipe**
1. Em **Equipe**, adicione operadores/gestores
2. Defina papéis conforme responsabilidade

**Assinatura**
1. Em **Conta / Billing**, veja trial e plano
2. Escolha Start / Pro / Business
3. Com Asaas configurado: checkout real  
4. Em ambiente de teste sem chave Asaas: confirmação local (uso interno/demo)

### 3.4 Login diário
Campos obrigatórios:
- E-mail  
- Senha  
- Identificador da empresa (slug)

---

## 4. Papéis (quem pode o quê — visão prática)

| Papel | Uso típico |
|-------|------------|
| **owner** | Dono da conta; billing, LLM, canais, equipe |
| **admin** | Administração operacional ampla |
| **manager** | Gestão de CRM, cobrança, campanhas, agentes |
| **operator** | Uso diário (inbox, consultas, operações) |
| **viewer** | Leitura / acompanhamento |

Escritas sensíveis (assinatura, chave LLM, canais) ficam restritas a **owner/admin**.

---

## 5. O que está pronto vs. o que depende de próximo passo

### Pronto para piloto / demonstração comercial
- Cadastro, login, trial, planos
- Agentes + base de conhecimento + chat de teste (com BYOK)
- CRM, cobrança interna, marketing (planejamento), equipe, dashboard
- Deploy em nuvem (Vercel + Neon + Render)

### Depende de configuração / infra extra
| Item | Necessário |
|------|------------|
| WhatsApp real | Evolution API hospedada (ex.: VPS) + chaves |
| Cobrança Asaas em produção | Chave live Asaas + webhook |
| Limites rígidos por plano | Evolução de produto (hoje os limites estão nos planos, enforcement completo ainda evolui) |
| Campanhas/cobrança 100% automáticas em fila | Worker de tarefas (hoje há modelo/status; execução full é roadmap) |

---

## 6. Resumo da jornada do cliente

```
Criar empresa → Trial 14 dias → Colar chave LLM → Subir FAQ
    → Ativar agentes → (Opcional) Conectar WhatsApp
    → Usar CRM / Cobrança / Marketing / Equipe
    → Assinar plano Start | Pro | Business
```

---

## 7. Mensagem comercial curta

> OperAI coloca uma equipe de IA na operação da PME: WhatsApp, cobrança e vendas com o conhecimento da empresa. Você traz a chave do modelo (BYOK); nós entregamos a plataforma, os agentes e o fluxo operacional — mensalidade previsível, sem surpresa de tokens embutidos.

---

*Documento alinhado ao estado atual do produto no monorepo OperAI (frontend + backend + deploy Vercel/Neon/Render).*
