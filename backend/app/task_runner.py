"""
Executor de AgentTask pendentes.
Processa tarefas enfileiradas (queued) e executa a lógica apropriada por tipo.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from .models import AgentTask, Agent, LlmCredential, ChannelMessage, InboxThread, Receivable
from .llm import chat, AGENT_SYSTEM_PROMPTS
from .database import async_session_maker


class TaskExecutionError(Exception):
    """Erro durante execução de uma tarefa."""
    pass


class TaskRunner:
    """Executor de tarefas pendentes."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def run_pending_tasks(self, limit: int = 10) -> list[dict[str, Any]]:
        """Busca e executa tarefas pendentes."""
        result = await self.db.execute(
            select(AgentTask)
            .where(AgentTask.status == "queued")
            .order_by(AgentTask.created_at)
            .limit(limit)
        )
        tasks = result.scalars().all()
        
        results = []
        for task in tasks:
            try:
                task_result = await self._execute_task(task)
                results.append({
                    "task_id": str(task.id),
                    "status": "completed",
                    "result": task_result
                })
            except Exception as e:
                await self._mark_task_failed(task, str(e))
                results.append({
                    "task_id": str(task.id),
                    "status": "failed",
                    "error": str(e)
                })
        
        return results
    
    async def _execute_task(self, task: AgentTask) -> dict[str, Any]:
        """Roteia para o handler apropriado baseado no tipo de tarefa."""
        handlers = {
            "whatsapp.reply": self._handle_whatsapp_reply,
            "finance.follow_up": self._handle_finance_follow_up,
            "marketing.campaign": self._handle_marketing_campaign,
            "marketing.handoff": self._handle_marketing_handoff,
            "marketing.crisis": self._handle_marketing_crisis,
        }
        
        handler = handlers.get(task.task_type)
        if not handler:
            raise TaskExecutionError(f"Tipo de tarefa desconhecido: {task.task_type}")
        
        # Marca como em execução
        await self._mark_task_running(task)
        
        # Executa
        result = await handler(task)
        
        # Marca como concluída
        await self._mark_task_completed(task, result)
        
        return result
    
    async def _handle_whatsapp_reply(self, task: AgentTask) -> dict[str, Any]:
        """Processa resposta automática de WhatsApp."""
        input_data = task.input_data or {}
        thread_id = input_data.get("thread_id")
        message_id = input_data.get("message_id")
        
        if not thread_id or not message_id:
            raise TaskExecutionError("Dados insuficientes para whatsapp.reply")
        
        # Busca a mensagem e thread
        result = await self.db.execute(
            select(ChannelMessage, InboxThread)
            .join(InboxThread, ChannelMessage.thread_id == InboxThread.id)
            .where(ChannelMessage.id == uuid.UUID(message_id))
        )
        row = result.first()
        if not row:
            raise TaskExecutionError(f"Mensagem {message_id} não encontrada")
        
        msg, thread = row
        
        # Busca credenciais LLM da organização
        cred_result = await self.db.execute(
            select(LlmCredential)
            .where(LlmCredential.organization_id == task.organization_id)
        )
        cred = cred_result.scalar_one_or_none()
        
        if not cred:
            raise TaskExecutionError("Credenciais LLM não configuradas")
        
        # Prepara contexto e chama LLM
        system_prompt = AGENT_SYSTEM_PROMPTS.get("whatsapp", AGENT_SYSTEM_PROMPTS["whatsapp"])
        user_message = msg.content or ""
        
        try:
            response = await chat(
                provider=cred.provider,
                api_key=cred.api_key_encrypted,  # TODO: descriptografar
                model=cred.model_name,
                system=system_prompt,
                user=user_message,
                temperature=0.3
            )
        except Exception as e:
            raise TaskExecutionError(f"Erro ao chamar LLM: {e}")
        
        # Cria mensagem de resposta
        reply_msg = ChannelMessage(
            organization_id=task.organization_id,
            channel_id=msg.channel_id,
            thread_id=thread.id,
            external_message_id=f"operai_reply_{datetime.now(timezone.utc).timestamp()}",
            direction="outbound",
            content=response,
            status="sent"
        )
        self.db.add(reply_msg)
        await self.db.commit()
        
        return {
            "reply_message_id": str(reply_msg.id),
            "content": response[:200] + "..." if len(response) > 200 else response
        }
    
    async def _handle_finance_follow_up(self, task: AgentTask) -> dict[str, Any]:
        """Processa follow-up de cobrança financeira."""
        input_data = task.input_data or {}
        receivable_id = input_data.get("receivable_id")
        
        if not receivable_id:
            raise TaskExecutionError("receivable_id não fornecido")
        
        # Busca o recebível
        result = await self.db.execute(
            select(Receivable)
            .where(Receivable.id == uuid.UUID(receivable_id))
        )
        receivable = result.scalar_one_or_none()
        
        if not receivable:
            raise TaskExecutionError(f"Recebível {receivable_id} não encontrado")
        
        # Prepara mensagem de follow-up baseada no status
        if receivable.status == "pending":
            days_to_due = (receivable.due_date - datetime.now().date()).days if receivable.due_date else None
            
            if days_to_due is not None and days_to_due > 0:
                follow_up_message = f"Olá, {receivable.customer_name}. Este é um lembrete amigável sobre a cobrança no valor de R$ {receivable.amount_cents/100:.2f} com vencimento em {receivable.due_date.strftime('%d/%m/%Y')}. Qualquer dúvida, estamos à disposição."
            else:
                follow_up_message = f"Prezado(a) {receivable.customer_name}, identificamos que a cobrança de R$ {receivable.amount_cents/100:.2f} está em atraso desde {receivable.due_date.strftime('%d/%m/%Y')}. Por favor, entre em contato conosco para regularizar a situação."
        else:
            follow_up_message = f"Cobrança {receivable.description or receivable.id} - Status: {receivable.status}"
        
        # TODO: Integração com WhatsApp para envio real da mensagem
        # Por enquanto, apenas registramos o resultado
        
        return {
            "receivable_id": receivable_id,
            "customer_name": receivable.customer_name,
            "amount_cents": receivable.amount_cents,
            "follow_up_message": follow_up_message,
            "status": "follow_up_generated",
            "note": "Integração com envio WhatsApp pendente - mensagem gerada mas não enviada automaticamente"
        }
    
    async def _handle_marketing_campaign(self, task: AgentTask) -> dict[str, Any]:
        """Processa progressão de campanha de marketing."""
        input_data = task.input_data or {}
        campaign_id = input_data.get("campaign_id")
        action = input_data.get("action", "progress")
        
        if not campaign_id:
            raise TaskExecutionError("campaign_id não fornecido")
        
        # Busca a campanha
        from .models import MarketingCampaign
        result = await self.db.execute(
            select(MarketingCampaign)
            .where(MarketingCampaign.id == uuid.UUID(campaign_id))
        )
        campaign = result.scalar_one_or_none()
        
        if not campaign:
            raise TaskExecutionError(f"Campanha {campaign_id} não encontrada")
        
        # Executa ação solicitada
        if action == "progress":
            # Atualiza contadores e verifica progresso
            old_status = campaign.status
            
            if campaign.status == "draft":
                campaign.status = "scheduled"
            elif campaign.status == "scheduled" and campaign.scheduled_at and campaign.scheduled_at <= datetime.now(timezone.utc):
                campaign.status = "sending"
            
            return {
                "campaign_id": campaign_id,
                "campaign_name": campaign.name,
                "previous_status": old_status,
                "current_status": campaign.status,
                "sent_count": campaign.sent_count,
                "delivered_count": campaign.delivered_count,
                "action": "progress"
            }
        
        elif action == "send_batch":
            # Simula envio de lote (integração real com provedor seria aqui)
            batch_size = input_data.get("batch_size", 100)
            
            return {
                "campaign_id": campaign_id,
                "action": "send_batch",
                "batch_size": batch_size,
                "note": "Integração com provedor de envio (Meta, Evolution, etc.) pendente - lote simulado mas não enviado"
            }
        
        else:
            raise TaskExecutionError(f"Ação desconhecida: {action}")
    
    async def _handle_marketing_handoff(self, task: AgentTask) -> dict[str, Any]:
        """Processa handoff de lead qualificado para equipe comercial."""
        input_data = task.input_data or {}
        lead_data = input_data.get("lead_data", {})
        
        if not lead_data:
            raise TaskExecutionError("lead_data não fornecido")
        
        # Extrai informações do lead
        contact_name = lead_data.get("name", "Não informado")
        contact_phone = lead_data.get("phone", "")
        contact_email = lead_data.get("email", "")
        interest = lead_data.get("interest", "Não especificado")
        urgency = lead_data.get("urgency", "normal")
        source_channel = lead_data.get("source_channel", "marketing")
        
        # Cria ou atualiza contato
        contact_result = await self.db.execute(
            select(Contact)
            .where(
                Contact.organization_id == task.organization_id,
                Contact.phone == contact_phone
            )
        )
        contact = contact_result.scalar_one_or_none()
        
        if not contact and contact_phone:
            contact = Contact(
                organization_id=task.organization_id,
                name=contact_name,
                phone=contact_phone
            )
            self.db.add(contact)
            await self.db.flush()
        
        # Cria oportunidade no CRM
        opportunity = Opportunity(
            organization_id=task.organization_id,
            company=contact_name if contact_name != "Não informado" else "Lead Marketing",
            contact=contact_name,
            stage="new",
            value_cents=0,
            source_title=f"Handoff Marketing: {interest}",
            source_channel=source_channel
        )
        self.db.add(opportunity)
        await self.db.commit()
        
        # Prepara notificação para equipe comercial
        handoff_summary = f"""
Novo Lead Qualificado - Handoff Marketing

Contato: {contact_name}
Telefone: {contact_phone}
Email: {contact_email}
Interesse: {interest}
Urgência: {urgency}
Origem: {source_channel}

Oportunidade criada no CRM. Pipeline: new
        """.strip()
        
        return {
            "handoff_type": "lead_qualified",
            "contact_id": str(contact.id) if contact else None,
            "opportunity_id": str(opportunity.id),
            "contact_name": contact_name,
            "contact_phone": contact_phone,
            "interest": interest,
            "urgency": urgency,
            "handoff_summary": handoff_summary,
            "note": "Lead qualificado encaminhado para comercial. Oportunidade criada no estágio 'new'."
        }
    
    async def _handle_marketing_crisis(self, task: AgentTask) -> dict[str, Any]:
        """Processa alerta de crise de reputação/engajamento."""
        input_data = task.input_data or {}
        crisis_data = input_data.get("crisis_data", {})
        
        if not crisis_data:
            raise TaskExecutionError("crisis_data não fornecido")
        
        # Extrai informações da crise
        crisis_type = crisis_data.get("type", "reputacao")
        severity = crisis_data.get("severity", "medium")
        channel = crisis_data.get("channel", "desconhecido")
        content_snippet = crisis_data.get("content_snippet", "")
        author = crisis_data.get("author", "Anônimo")
        
        # Prepara relatório de crise
        crisis_report = f"""
ALERTA DE CRISE - {crisis_type.upper()}

Severidade: {severity}
Canal: {channel}
Autor: {author}

Resumo do Conteúdo:
{content_snippet[:500]}{"..." if len(content_snippet) > 500 else ""}

Ações Recomendadas:
"""
        
        if severity == "high":
            crisis_report += "- URGENTE: Acionar gestor imediatamente\n"
            crisis_report += "- Preparar resposta oficial em até 1 hora\n"
            crisis_report += "- Monitorar menções e comentários relacionados\n"
        elif severity == "medium":
            crisis_report += "- Avaliar contexto completo antes de responder\n"
            crisis_report += "- Preparar resposta em até 4 horas\n"
            crisis_report += "- Considerar abordagem educativa e solução proativa\n"
        else:
            crisis_report += "- Monitorar evolução da situação\n"
            crisis_report += "- Preparar resposta padrão caso escale\n"
        
        return {
            "crisis_type": crisis_type,
            "severity": severity,
            "channel": channel,
            "author": author,
            "crisis_report": crisis_report,
            "requires_immediate_action": severity == "high",
            "note": f"Alerta de crise ({crisis_type}) processado. Severidade: {severity}. Gestor deve ser notificado se 'high'."
        }
    
    # Helpers
    
    async def _mark_task_running(self, task: AgentTask) -> None:
        """Marca tarefa como em execução."""
        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        await self.db.commit()
    
    async def _mark_task_completed(self, task: AgentTask, result: dict) -> None:
        """Marca tarefa como concluída."""
        task.status = "completed"
        task.result_data = result
        task.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
    
    async def _mark_task_failed(self, task: AgentTask, error: str) -> None:
        """Marca tarefa como falha."""
        task.status = "failed"
        task.error = error[:1000]  # Limita tamanho do erro
        task.completed_at = datetime.now(timezone.utc)
        await self.db.commit()


# Funções de conveniência para uso externo

async def run_pending_tasks(limit: int = 10) -> list[dict[str, Any]]:
    """Executa tarefas pendentes (convenience function)."""
    async with async_session_maker() as db:
        runner = TaskRunner(db)
        return await runner.run_pending_tasks(limit)


async def execute_single_task(task_id: uuid.UUID) -> dict[str, Any]:
    """Executa uma tarefa específica pelo ID."""
    async with async_session_maker() as db:
        runner = TaskRunner(db)
        
        result = await db.execute(
            select(AgentTask).where(AgentTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        
        if not task:
            raise TaskExecutionError(f"Tarefa {task_id} não encontrada")
        
        if task.status != "queued":
            raise TaskExecutionError(f"Tarefa não está em estado 'queued' (estado atual: {task.status})")
        
        try:
            task_result = await runner._execute_task(task)
            return {
                "task_id": str(task_id),
                "status": "completed",
                "result": task_result
            }
        except Exception as e:
            await runner._mark_task_failed(task, str(e))
            raise
