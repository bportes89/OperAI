/// <reference types="cypress" />

describe('Authentication - Login', () => {
  beforeEach(() => {
    cy.visit('/login')
  })

  it('should display login form correctly', () => {
    cy.get('input[type="email"]').should('be.visible')
    cy.get('input[type="password"]').should('be.visible')
    cy.get('button[type="submit"]').should('be.visible').and('contain', 'Entrar')
  })

  it('should show error for invalid credentials', () => {
    cy.get('input[type="email"]').type('invalid@example.com')
    cy.get('input[type="password"]').type('wrongpassword')
    cy.get('button[type="submit"]').click()

    cy.contains('Credenciais inválidas', { timeout: 5000 }).should('be.visible')
  })

  it('should successfully login with valid credentials', () => {
    // Usa comando customizado de autenticação
    cy.login()

    // Verifica redirecionamento para o app
    cy.url().should('include', '/app')
    cy.contains('Dashboard', { timeout: 10000 }).should('be.visible')
  })

  it('should persist session after page reload', () => {
    cy.login()
    cy.visit('/app')
    cy.reload()
    cy.contains('Dashboard', { timeout: 10000 }).should('be.visible')
  })

  it('should navigate to forgot password page', () => {
    cy.contains('Esqueceu sua senha?').click()
    cy.url().should('include', '/forgot-password')
    cy.contains('Recuperar senha').should('be.visible')
  })
})
