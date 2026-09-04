# Configuração de Proteção da Branch `main`

Este guia explica como configurar a proteção da branch `main` no GitHub para garantir qualidade de código antes de permitir merges.

## 🎯 Objetivo

Impedir que código quebrado ou não testado seja mergeado na branch principal, garantindo que:

- Todos os testes passem
- O código seja revisado por pelo menos uma pessoa
- Não haja conflitos de merge

## ⚙️ Passo a Passo

### 1. Acesse as Configurações do Repositório

1. Vá para: `https://github.com/bportes89/OperAI/settings`
2. No menu lateral, clique em **"Branches"** (ou acesse diretamente: `https://github.com/bportes89/OperAI/settings/branches`)

### 2. Adicione uma Regra de Proteção

1. Clique no botão **"Add rule"** (ou "Adicionar regra")
2. Em **"Branch name pattern"**, digite: `main`
3. Configure as opções conforme abaixo:

#### ✅ Regras Obrigatórias (Required)

| Opção | Configuração | Descrição |
|-------|--------------|-----------|
| **Require a pull request before merging** | ✅ Ativado | Exige que todas as mudanças passem por um PR |
| ↳ Require approvals | `1` | Número mínimo de aprovações necessárias |
| ↳ Dismiss stale PR approvals when new commits are pushed | ✅ Ativado | Requer nova aprovação se houver novos commits |
| **Require status checks to pass before merging** | ✅ Ativado | Exige que os checks do CI passem |
| ↳ Require branches to be up to date before merging | ✅ Ativado | Exige que a branch esteja atualizada com a main |
| ↳ Status checks that are required | Busque e selecione: | Escolha os workflows que devem passar |
| | `ci / test-backend (3.12)` | Testes do backend |
| | `ci / test-frontend` | Build e lint do frontend |
| | `e2e / e2e` | Testes end-to-end |

#### 🔒 Regras Adicionais Recomendadas

| Opção | Configuração | Descrição |
|-------|--------------|-----------|
| **Require conversation resolution before merging** | ✅ Ativado | Exige que todas as conversas em reviews sejam resolvidas |
| **Include administrators** | ⚠️ Opcional | Aplica as mesmas regras para administradores |
| **Restrict pushes that create large files** | ✅ Ativado | Impede commit de arquivos grandes (>100MB) |
| **Require signed commits** | ⚠️ Opcional | Exige que todos os commits sejam assinados GPG |

### 3. Salve a Regra

1. Revise todas as configurações
2. Clique em **"Create"** (ou "Criar") para salvar a regra de proteção

## ✅ Verificação

Para verificar se a proteção está funcionando:

1. Crie uma nova branch: `git checkout -b test-protection`
2. Faça uma alteração e commite: `git commit -am "Teste de proteção"`
3. Tente fazer push direto para a main: `git push origin main`
   - ❌ Deve falhar com erro de proteção de branch
4. Faça push para a branch de teste: `git push origin test-protection`
5. Crie um Pull Request no GitHub
   - ✅ O PR deve exibir os checks do CI
   - ✅ Deve exigir aprovação antes do merge

## 🔧 Resolução de Problemas

### Erro: "Changes must be made through a pull request"

**Causa:** Tentativa de push direto na `main`.

**Solução:**
1. Crie uma branch: `git checkout -b minha-feature`
2. Faça as alterações e commit
3. Push para a branch: `git push origin minha-feature`
4. Crie um PR no GitHub

### Erro: "Required status check is expected"

**Causa:** O workflow do CI não está rodando ou falhou.

**Solução:**
1. Verifique a aba "Actions" no GitHub
2. Corrija os erros nos testes
3. Faça push das correções
4. Aguarde os checks passarem

### Erro: "Review required"

**Causa:** Nenhuma aprovação no PR.

**Solução:**
1. Solicite review de um colega
2. Após aprovação, o botão de merge será habilitado

## 📚 Recursos Adicionais

- [GitHub Docs - About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub Docs - Managing a branch protection rule](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule)
- [Cypress Best Practices](https://docs.cypress.io/guides/references/best-practices)
- [Pytest Documentation](https://docs.pytest.org/)
