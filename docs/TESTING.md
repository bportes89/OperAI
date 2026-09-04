# Guia de Testes do OperAI

Este guia explica como adicionar e executar testes no projeto OperAI.

## 📁 Estrutura de Testes

```
backend/
└── tests/
    ├── conftest.py           # Configurações e fixtures compartilhadas
    ├── test_api_tasks.py     # Testes de API para tarefas
    ├── test_scheduler.py     # Testes do agendador
    ├── test_task_runner.py   # Testes do executor de tarefas
    └── test_websocket.py     # Testes de WebSocket

frontend/
└── cypress/
    ├── e2e/
    │   ├── auth/
    │   │   └── login.cy.ts   # Testes de login
    │   └── dashboard.cy.ts  # Testes do dashboard
    ├── fixtures/
    │   └── auth.json         # Dados mock para testes
    └── support/
        ├── commands.ts       # Comandos customizados do Cypress
        └── e2e.ts            # Configuração global
```

## 🧪 Testes Backend (Pytest)

### Executar Todos os Testes

```bash
cd backend
pytest
```

### Executar com Saída Detalhada

```bash
pytest -v
```

### Executar Teste Específico

```bash
pytest tests/test_api_tasks.py
pytest tests/test_scheduler.py::TestSchedulerLifecycle
```

### Executar com Coverage

```bash
pytest --cov=app --cov-report=html
```

### Fixtures Disponíveis

O arquivo `conftest.py` fornece as seguintes fixtures:

- `db_session` — Sessão do banco de dados para testes
- `async_client` — Cliente HTTP assíncrono para testes de API
- `auth_headers` — Headers de autenticação JWT para requests autenticados
- `test_organization` — Organização de teste
- `test_user` — Usuário de teste

Exemplo de uso:

```python
async def test_minha_feature(async_client: AsyncClient, auth_headers: dict):
    response = await async_client.get("/api/v1/minha-rota", headers=auth_headers)
    assert response.status_code == 200
```

## 🌐 Testes E2E (Cypress)

### Executar Todos os Testes E2E

```bash
cd frontend
npx cypress run
```

### Abrir Cypress em Modo Interativo

```bash
cd frontend
npx cypress open
```

### Executar Teste Específico

```bash
npx cypress run --spec "cypress/e2e/auth/login.cy.ts"
```

### Comandos Customizados

Os comandos customizados estão definidos em `cypress/support/commands.ts`:

- `cy.login(email?, password?)` — Realiza login via UI e armazena token
- `cy.logout()` — Realiza logout e limpa estado
- `cy.waitForApi(alias)` — Aguarda requisição API interceptada
- `cy.fillByTestId(testId, value)` — Preenche campo por data-testid
- `cy.clickByTestId(testId)` — Clica em elemento por data-testid

Exemplo de uso:

```typescript
describe('Minha Feature', () => {
  beforeEach(() => {
    cy.login() // Usa credenciais da fixture
    cy.visit('/app/minha-feature')
  })

  it('should create new item', () => {
    cy.clickByTestId('new-item-btn')
    cy.fillByTestId('item-name-input', 'Novo Item')
    cy.clickByTestId('save-item-btn')

    cy.contains('Item criado com sucesso').should('be.visible')
  })
})
```

## ➕ Adicionando Novos Testes

### Backend (Pytest)

1. Crie um novo arquivo em `backend/tests/test_<feature>.py`
2. Use as fixtures do `conftest.py` quando necessário
3. Siga o padrão: Arrange → Act → Assert

Exemplo:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_criar_nova_tarefa(async_client: AsyncClient, auth_headers: dict):
    # Arrange
    payload = {
        "task_type": "marketing.campaign",
        "title": "Campanha Teste",
        "priority": "high"
    }

    # Act
    response = await async_client.post(
        "/api/v1/tasks",
        json=payload,
        headers=auth_headers
    )

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Campanha Teste"
    assert data["status"] == "queued"
```

### Frontend (Cypress)

1. Crie um novo arquivo em `frontend/cypress/e2e/<pasta>/<teste>.cy.ts`
2. Use os comandos customizados para login/autenticação
3. Use `data-testid` nos componentes para seletores estáveis

Exemplo:

```typescript
describe('Configurações de LLM', () => {
  beforeEach(() => {
    cy.login()
    cy.visit('/app/settings/llm')
  })

  it('should display LLM settings form', () => {
    cy.contains('Configurações de IA').should('be.visible')
    cy.get('[data-testid="llm-provider-select"]').should('be.visible')
    cy.get('[data-testid="api-key-input"]').should('be.visible')
  })

  it('should save LLM configuration', () => {
    cy.get('[data-testid="llm-provider-select"]').select('groq')
    cy.get('[data-testid="model-select"]').select('llama-3.3-70b-versatile')
    cy.get('[data-testid="api-key-input"]').type('gsk_test123456789', { log: false })
    
    cy.get('[data-testid="save-settings-btn"]').click()
    
    cy.contains('Configurações salvas', { timeout: 5000 }).should('be.visible')
  })
})
```

## 🔧 Dicas para Testes Robustos

1. **Evite sleeps/fixos** — Use `cy.intercept()` para aguardar requests
2. **Seletores estáveis** — Prefira `data-testid` sobre classes/IDs que mudam
3. **Limpeza** — Sempre limpe dados de teste no `afterEach`
4. **Fixtures** — Use arquivos JSON em `cypress/fixtures/` para dados de teste

## 🐛 Debugging

- Use `cy.pause()` para parar em um ponto específico
- No modo interativo (`cypress open`), use o time-travel para ver estados anteriores
- Habilite logging detalhado: `DEBUG=cypress:* npx cypress run`

---

Para mais detalhes, consulte:
- [Documentação do Pytest](https://docs.pytest.org/)
- [Documentação do Cypress](https://docs.cypress.io/)
