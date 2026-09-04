import pytest
from datetime import datetime
from uuid import uuid4

from httpx import AsyncClient

from app.models import AgentTask, Organization, User


class TestTasksEndpoints:
    pass

    async def test_list_pending_tasks_empty(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        response = await async_client.get(
            "/api/v1/tasks/pending",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tasks"] == []
        assert data["pagination"]["total"] == 0

    async def test_list_pending_tasks_with_data(
        self, async_client: AsyncClient, auth_headers: dict,
        test_organization: Organization, test_user: User,
        db_session
    ):
        tasks = []
        for i in range(3):
            task = AgentTask(
                id=uuid4(),
                organization_id=test_organization.id,
                task_type="marketing.crisis",
                title=f"Test Task {i}",
                priority="normal",
                status="queued",
                input_data={"crisis_data": {"type": "reputacao", "severity": "low"}},
                created_at=datetime.utcnow(),
                created_by=test_user.id
            )
            db_session.add(task)
            tasks.append(task)
        
        await db_session.commit()

        # Lista tarefas
        response = await async_client.get(
            "/api/v1/tasks/pending?limit=10",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 3
        assert data["pagination"]["total"] == 3

    async def test_run_pending_tasks(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        response = await async_client.post(
            "/api/v1/tasks/run-pending?limit=5",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "processed" in data
        assert "results" in data

    async def test_execute_single_task(
        self, async_client: AsyncClient, auth_headers: dict,
        test_organization: Organization, test_user: User,
        db_session
    ):
        task = AgentTask(
            id=uuid4(),
            organization_id=test_organization.id,
            task_type="marketing.crisis",
            title="Test Execute Task",
            priority="high",
            status="queued",
            input_data={"crisis_data": {"type": "reputacao", "severity": "high"}},
            created_at=datetime.utcnow(),
            created_by=test_user.id
        )
        db_session.add(task)
        await db_session.commit()

        # Executa tarefa
        response = await async_client.post(
            f"/api/v1/tasks/{task.id}/execute",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == str(task.id)
        assert data["status"] == "completed"

    async def test_execute_nonexistent_task(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        fake_id = uuid4()
        
        response = await async_client.post(
            f"/api/v1/tasks/{fake_id}/execute",
            headers=auth_headers
        )

        assert response.status_code == 404

    async def test_list_tasks_unauthorized(
        self, async_client: AsyncClient
    ):
        response = await async_client.get("/api/v1/tasks/pending")
        
        assert response.status_code == 401
