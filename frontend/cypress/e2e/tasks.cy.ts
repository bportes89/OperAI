/// <reference types="cypress" />

describe('Tasks Management', () => {
  beforeEach(() => {
    cy.login()
    cy.visit('/app/tasks')
  })

  it('should display tasks page correctly', () => {
    cy.contains('Gerenciamento de Tarefas').should('be.visible')
    cy.get('[data-testid="tasks-list"]').should('be.visible')
    cy.get('[data-testid="task-filters"]').should('be.visible')
  })

  it('should filter tasks by status', () => {
    cy.get('[data-testid="status-filter"]').click()
    cy.contains('Pendente').click()
    
    cy.get('[data-testid="tasks-list"]').within(() => {
      cy.get('[data-testid="task-status"]').each(($el) => {
        expect($el.text()).to.include('Pendente')
      })
    })
  })

  it('should create a new task', () => {
    cy.get('[data-testid="new-task-btn"]').click()
    
    cy.get('[data-testid="task-modal"]').within(() => {
      cy.get('[data-testid="task-title-input"]').type('Tarefa de Teste')
      cy.get('[data-testid="task-type-select"]').select('marketing.campaign')
      cy.get('[data-testid="task-priority-select"]').select('high')
      cy.get('[data-testid="save-task-btn"]').click()
    })
    
    cy.contains('Tarefa criada com sucesso').should('be.visible')
    cy.contains('Tarefa de Teste').should('be.visible')
  })

  it('should execute a pending task', () => {
    // Cria uma tarefa pendente
    cy.createTask({
      title: 'Tarefa para Executar',
      type: 'marketing.crisis',
      priority: 'normal'
    })
    
    cy.reload()
    
    // Encontra e executa a tarefa
    cy.contains('Tarefa para Executar')
      .parents('[data-testid="task-item"]')
      .within(() => {
        cy.get('[data-testid="execute-task-btn"]').click()
      })
    
    cy.contains('Executando...').should('be.visible')
    cy.contains('Concluído', { timeout: 30000 }).should('be.visible')
  })

  it('should display task details', () => {
    cy.createTask({
      title: 'Tarefa com Detalhes',
      type: 'finance.followup',
      priority: 'high'
    })
    
    cy.contains('Tarefa com Detalhes').click()
    
    cy.get('[data-testid="task-detail-modal"]').within(() => {
      cy.contains('Tarefa com Detalhes').should('be.visible')
      cy.contains('finance.followup').should('be.visible')
      cy.contains('Alta').should('be.visible')
      cy.get('[data-testid="close-modal-btn"]').click()
    })
    
    cy.get('[data-testid="task-detail-modal"]').should('not.exist')
  })
})
