import pytest
from uuid import uuid4

from app.models import AgentTask
from app.task_runner import TaskExecutionError, TaskRunner


@pytest.mark.asyncio
async def test_run_pending_tasks_empty(db_session):
    runner = TaskRunner(db_session)
    results = await runner.run_pending_tasks(limit=10)
    assert results == []


@pytest.mark.asyncio
async def test_execute_unknown_task_type_marks_failed(db_session, test_organization, test_user):
    task = AgentTask(
        id=uuid4(),
        organization_id=test_organization.id,
        task_type="unknown.type",
        title="Unknown task",
        priority="normal",
        status="queued",
        input_data={},
        created_by=test_user.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    runner = TaskRunner(db_session)
    results = await runner.run_pending_tasks(limit=10)
    assert len(results) == 1
    assert results[0]["status"] == "failed"

    await db_session.refresh(task)
    assert task.status == "failed"
    assert "Tipo de tarefa desconhecido" in (task.error or "")


@pytest.mark.asyncio
async def test_execute_marketing_crisis_success(db_session, test_organization, test_user):
    task = AgentTask(
        id=uuid4(),
        organization_id=test_organization.id,
        task_type="marketing.crisis",
        title="Crisis task",
        priority="normal",
        status="queued",
        input_data={"crisis_data": {"type": "reputacao", "severity": "low", "channel": "ig"}},
        created_by=test_user.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    runner = TaskRunner(db_session)
    result = await runner._execute_task(task)
    assert result["severity"] == "low"

    await db_session.refresh(task)
    assert task.status == "completed"
