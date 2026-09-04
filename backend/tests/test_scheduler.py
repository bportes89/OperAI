import pytest
from unittest.mock import patch, AsyncMock

import app.scheduler as scheduler_mod


class TestSchedulerLifecycle:
    @pytest.mark.asyncio
    async def test_start_scheduler_initializes_correctly(self):
        if scheduler_mod._scheduler is not None and scheduler_mod._scheduler.running:
            scheduler_mod._scheduler.shutdown()
            scheduler_mod._scheduler = None

        result = scheduler_mod.start_scheduler(interval_minutes=5)

        assert result is not None
        assert result.running is True

        result.shutdown()
        scheduler_mod._scheduler = None

    @pytest.mark.asyncio
    async def test_start_scheduler_already_running(self):
        first_scheduler = scheduler_mod.start_scheduler(interval_minutes=5)
        second_scheduler = scheduler_mod.start_scheduler(interval_minutes=5)

        assert second_scheduler is first_scheduler

        first_scheduler.shutdown()
        scheduler_mod._scheduler = None

    @pytest.mark.asyncio
    async def test_stop_scheduler_correctly(self):
        scheduler = scheduler_mod.start_scheduler(interval_minutes=5)
        assert scheduler.running is True

        scheduler_mod.stop_scheduler()
        assert scheduler_mod._scheduler is None

    @pytest.mark.asyncio
    async def test_stop_scheduler_not_running(self):
        scheduler_mod._scheduler = None
        scheduler_mod.stop_scheduler()


class TestSchedulerStatus:
    def test_get_status_not_initialized(self):
        scheduler_mod._scheduler = None
        status = scheduler_mod.get_scheduler_status()
        assert status["status"] == "not_initialized"
        assert status["running"] is False

    @pytest.mark.asyncio
    async def test_get_status_running(self):
        scheduler = scheduler_mod.start_scheduler(interval_minutes=5)
        status = scheduler_mod.get_scheduler_status()
        assert status["status"] == "running"
        assert status["running"] is True
        assert "jobs" in status
        scheduler.shutdown()
        scheduler_mod._scheduler = None

    @pytest.mark.asyncio
    async def test_get_status_stopped(self):
        scheduler = scheduler_mod.start_scheduler(interval_minutes=5)
        scheduler_mod.stop_scheduler()
        status = scheduler_mod.get_scheduler_status()
        assert status["status"] == "not_initialized"
        assert status["running"] is False
        scheduler_mod._scheduler = None


class TestExecutePendingTasksJob:
    """Testes para o job de execução de tarefas."""

    @pytest.mark.asyncio
    async def test_execute_pending_tasks_job_success(self):
        """Testa execução bem-sucedida do job."""
        with patch('app.scheduler.run_pending_tasks', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = [
                {"task_id": "1", "status": "completed"},
                {"task_id": "2", "status": "completed"}
            ]

            await scheduler_mod._execute_pending_tasks_job()

            mock_run.assert_called_once_with(limit=20)

    @pytest.mark.asyncio
    async def test_execute_pending_tasks_job_with_failures(self):
        """Testa execução do job com algumas falhas."""
        with patch('app.scheduler.run_pending_tasks', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = [
                {"task_id": "1", "status": "completed"},
                {"task_id": "2", "status": "failed", "error": "API Error"}
            ]

            await scheduler_mod._execute_pending_tasks_job()

            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_pending_tasks_job_exception(self):
        """Testa execução do job quando ocorre exceção."""
        with patch('app.scheduler.run_pending_tasks', new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = Exception("Database connection error")

            await scheduler_mod._execute_pending_tasks_job()

            mock_run.assert_called_once()
