/// <reference types="cypress" />
// ***********************************************************
// This example support/e2e.ts is processed and
// loaded automatically before your test files.
//
// This is a great place to put global configuration and
// behavior that modifies Cypress.
//
// You can change the location of this file or turn off
// automatically serving support files with the
// 'supportFile' configuration option.
//
// You can read more here:
// https://on.cypress.io/configuration
// ***********************************************************

// Import commands.ts using ES2015 syntax:
import './commands'

// Alternatively you can use CommonJS syntax:
// require('./commands')

// Configuração global do Cypress
cypress.on('uncaught:exception', (err, runnable) => {
  // Ignora erros de exceção não capturados que não afetam os testes
  if (err.message.includes('ResizeObserver')) {
    return false
  }
  return true
})

// Configuração de viewport padrão
Cypress.config('viewportWidth', 1280)
Cypress.config('viewportHeight', 720)

// Timeout padrão para requisições
Cypress.config('defaultCommandTimeout', 10000)
Cypress.config('requestTimeout', 10000)
