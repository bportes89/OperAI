/// <reference types="cypress" />

// ***********************************************
// This example commands.ts shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************

// -- This is a parent command --
// Cypress.Commands.add('login', (email, password) => { ... })
//
// -- This is a child command --
// Cypress.Commands.add('drag', { prevSubject: 'element'}, (subject, options) => { ... })
//
// -- This is a dual command --
// Cypress.Commands.add('dismiss', { prevSubject: 'optional'}, (subject, options) => { ... })
//
// -- This will overwrite an existing command --
// Cypress.Commands.overwrite('visit', (originalFn, url, options) => { ... })

import { loginCredentials } from '../fixtures/auth.json'

declare global {
  namespace Cypress {
    interface Chainable {
      /**
       * Realiza login via API e armazena o token
       * @param email - Email do usuário (opcional, usa fixture por padrão)
       * @param password - Senha do usuário (opcional, usa fixture por padrão)
       * @example cy.login() // Usa credenciais da fixture
       * @example cy.login('user@test.com', 'password123')
       */
      login(email?: string, password?: string): Chainable<void>

      /**
       * Realiza logout e limpa o estado de autenticação
       * @example cy.logout()
       */
      logout(): Chainable<void>

      /**
       * Aguarda uma requisição API interceptada
       * @param alias - Alias da interceptação
       * @example cy.waitForApi('@loginRequest')
       */
      waitForApi(alias: string): Chainable<Intercept>

      /**
       * Preenche um campo de formulário com data-testid
       * @param testId - Data-testid do campo
       * @param value - Valor a ser preenchido
       * @example cy.fillByTestId('email-input', 'user@test.com')
       */
      fillByTestId(testId: string, value: string): Chainable<void>

      /**
       * Clica em um elemento por data-testid
       * @param testId - Data-testid do elemento
       * @example cy.clickByTestId('submit-button')
       */
      clickByTestId(testId: string): Chainable<void>
    }
  }
}

// Comando de login
Cypress.Commands.add('login', (email?: string, password?: string) => {
  const userEmail = email || loginCredentials.email
  const userPassword = password || loginCredentials.password

  // Intercepta a requisição de login
  cy.intercept('POST', '**/auth/login').as('loginRequest')

  // Realiza login via UI
  cy.visit('/login')
  cy.fillByTestId('email-input', userEmail)
  cy.fillByTestId('password-input', userPassword)
  cy.clickByTestId('login-submit')

  // Aguarda a requisição completar
  cy.waitForApi('@loginRequest').its('response.statusCode').should('eq', 200)

  // Verifica redirecionamento
  cy.url().should('include', '/app')
})

// Comando de logout
Cypress.Commands.add('logout', () => {
  // Limpa localStorage e cookies
  cy.window().then((win) => {
    win.localStorage.clear()
  })
  cy.clearCookies()
  cy.clearLocalStorage()

  // Visita página de login
  cy.visit('/login')
})

// Comando para aguardar API
Cypress.Commands.add('waitForApi', (alias: string) => {
  return cy.wait(alias, { timeout: 10000 })
})

// Comando para preencher campo por data-testid
Cypress.Commands.add('fillByTestId', (testId: string, value: string) => {
  cy.get(`[data-testid="${testId}"]`).should('be.visible').clear().type(value)
})

// Comando para clicar por data-testid
Cypress.Commands.add('clickByTestId', (testId: string) => {
  cy.get(`[data-testid="${testId}"]`).should('be.visible').click()
})
