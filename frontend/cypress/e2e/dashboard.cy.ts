/// <reference types="cypress" />

describe('Dashboard', () => {
  beforeEach(() => {
    cy.login()
    cy.visit('/app')
  })

  it('should display dashboard layout correctly', () => {
    // Verifica header
    cy.contains('Dashboard').should('be.visible')

    // Verifica navegação lateral
    cy.get('nav').should('be.visible')
    cy.contains('Tarefas').should('be.visible')
    cy.contains('Configurações').should('be.visible')
  })

  it('should display metrics cards', () => {
    cy.get('[data-testid="metrics-grid"]', { timeout: 10000 }).should('be.visible')
    cy.contains('Total de Tarefas').should('be.visible')
    cy.contains('Pendentes').should('be.visible')
    cy.contains('Concluídas').should('be.visible')
  })

  it('should navigate to tasks page', () => {
    cy.contains('Tarefas').click()
    cy.url().should('include', '/app/tasks')
    cy.contains('Gerenciamento de Tarefas').should('be.visible')
  })

  it('should navigate to settings page', () => {
    cy.contains('Configurações').click()
    cy.url().should('include', '/app/settings')
    cy.contains('Configurações').should('be.visible')
  })

  it('should handle logout', () => {
    cy.contains('Sair').click()
    cy.url().should('include', '/login')
    cy.contains('Entrar').should('be.visible')

    // Verifica que não pode acessar app sem login
    cy.visit('/app')
    cy.url().should('include', '/login')
  })
})
