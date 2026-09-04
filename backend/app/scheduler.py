"""
Agendador automático de tarefas usando APScheduler.
Executa o processamento de AgentTask pendentes periodicamente.
"""
import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .task_runner import run_pending_tasks

logger = logging.getLogger(__name__)

# Scheduler global
_scheduler: AsyncIOScheduler | None = None


async def _execute_pending_tasks_job():
    """Job que executa tarefas pendentes."""
    try:
        logger.info(f"[Scheduler] Starting task execution at {datetime.now(timezone.utc)}")
        results = await run_pending_tasks(limit=20)
        
        completed = sum(1 for r in results if r.get("status") == "completed")
        failed = sum(1 for r in results if r.get("status") == "failed")
        
        logger.info(
            f"[Scheduler] Task execution completed: "
            f"{completed} completed, {failed} failed, "
            f"{len(results)} total"
        )
        
    except Exception as e:
        logger.error(f"[Scheduler] Error executing pending tasks: {e}", exc_info=True)


def start_scheduler(
    interval_minutes: int = 5,
    max_instances: int = 1
) -> AsyncIOScheduler | None:
    """
    Inicia o agendador automático de tarefas.
    
    Args:
        interval_minutes: Intervalo em minutos entre execuções (padrão: 5)
        max_instances: Máximo de instâncias concorrentes do job
    
    Returns:
        Instância do scheduler iniciado ou None se já estiver rodando
    """
    global _scheduler
    
    if _scheduler is not None and _scheduler.running:
        logger.warning("[Scheduler] Scheduler already running, skipping start")
        return _scheduler
    
    try:
        # Cria o scheduler com configuração segura para containers
        # O scheduler vai usar o event loop padrão (não manipulamos explicitamente)
        _scheduler = AsyncIOScheduler(
            job_defaults={
                'coalesce': True,
                'max_instances': max_instances,
                'misfire_grace_time': 300
            }
        )
        
        # Configura o job de execução de tarefas pendentes
        _scheduler.add_job(
            _execute_pending_tasks_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id="execute_pending_tasks",
            name="Execute Pending AgentTasks",
            max_instances=max_instances,
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=300
        )
        
        _scheduler.start()
        logger.info(
            f"[Scheduler] Started successfully. "
            f"Job 'execute_pending_tasks' will run every {interval_minutes} minutes"
        )
        
        return _scheduler
        
    except Exception as e:
        logger.error(f"[Scheduler] Failed to start: {e}", exc_info=True)
        _scheduler = None
        return None


def stop_scheduler():
    """Para o agendador."""
    global _scheduler
    
    if _scheduler is None or not _scheduler.running:
        logger.warning("[Scheduler] Scheduler not running, nothing to stop")
        return
    
    try:
        _scheduler.shutdown(wait=True)
        logger.info("[Scheduler] Stopped successfully")
    except Exception as e:
        logger.error(f"[Scheduler] Error stopping: {e}", exc_info=True)
    finally:
        _scheduler = None


def get_scheduler_status() -> dict:
    """Retorna status atual do scheduler."""
    global _scheduler
    
    if _scheduler is None:
        return {"status": "not_initialized", "running": False}
    
    jobs_info = []
    if _scheduler.running:
        try:
            for job in _scheduler.get_jobs():
                jobs_info.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                })
        except Exception as e:
            logger.error(f"[Scheduler] Error getting job info: {e}")
    
    return {
        "status": "running" if _scheduler.running else "stopped",
        "running": _scheduler.running,
        "jobs": jobs_info
    }