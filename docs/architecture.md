# Arquitetura da Fase 1

O frontend Next.js consome a API FastAPI. O PostgreSQL é a fonte de verdade. Cada token de acesso contém `sub`, `org` e `role`. A API extrai o tenant do token; endpoints não aceitam um `organization_id` arbitrário enviado pelo cliente.

## Regras

- Toda tabela de negócio possui `organization_id` e índice tenant-first.
- Refresh tokens são aleatórios, armazenados apenas como SHA-256 e rotacionados a cada uso.
- RBAC é validado no servidor.
- Escritas sensíveis produzem auditoria.
- O frontend nunca decide autorização.
