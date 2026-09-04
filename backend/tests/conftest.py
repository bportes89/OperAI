import pytest
import pytest_asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator, Generator
from uuid import uuid4

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.core.database import get_session
from app.core.security import create_access_token
from app.models import AgentTask, Base, Membership, Organization, Role, User


# =============================================================================
# Configuração de Banco de Dados para Testes
# =============================================================================

# Usa SQLite em memória para testes (mais rápido)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Engine de teste
_test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,  # Desabilita logs SQL durante testes
    future=True
)

# Session maker de teste
TestAsyncSession = async_sessionmaker(
    _test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def create_test_tables():
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_test_tables():
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# =============================================================================
# Fixtures
# =============================================================================

@pytest_asyncio.fixture(scope="session")
async def db_engine():
    await create_test_tables()
    yield _test_engine
    await drop_test_tables()
    await _test_engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    async with TestAsyncSession() as session:
        yield session
        await session.rollback()


@pytest.fixture
def test_client(db_session) -> Generator[TestClient, None, None]:
    async def override_get_session():
        yield db_session
    
    app.dependency_overrides[get_session] = override_get_session
    
    with TestClient(app) as client:
        yield client
    
    # Limpa o override após o teste
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(db_session) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_session():
        yield db_session
    
    app.dependency_overrides[get_session] = override_get_session
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    
    # Limpa o override após o teste
    app.dependency_overrides.clear()


# =============================================================================
# Fixtures de Dados de Teste
# =============================================================================

@pytest_asyncio.fixture
async def test_organization(db_session: AsyncSession) -> Organization:
    org = Organization(
        id=uuid4(),
        name="Test Organization",
        slug=f"test-org-{uuid4().hex[:8]}",
        active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_organization: Organization) -> User:
    user = User(
        id=uuid4(),
        email=f"test-{uuid4().hex[:8]}@example.com",
        name="Test User",
        password_hash="hashed_password_here",
        active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    membership = Membership(
        id=uuid4(),
        user_id=user.id,
        organization_id=test_organization.id,
        role=Role.OWNER,
        active=True,
    )
    db_session.add(membership)
    await db_session.commit()
    
    return user


@pytest_asyncio.fixture
async def test_task(db_session: AsyncSession, test_organization: Organization, test_user: User) -> AgentTask:
    task = AgentTask(
        id=uuid4(),
        organization_id=test_organization.id,
        task_type="whatsapp.reply",
        title="Test WhatsApp Reply Task",
        priority="normal",
        status="queued",
        input_data={"thread_id": str(uuid4()), "message_id": str(uuid4())},
        created_by=test_user.id
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


@pytest.fixture
def auth_headers(test_user: User, test_organization: Organization) -> dict:
    token = create_access_token(
        user_id=str(test_user.id),
        organization_id=str(test_organization.id),
        role="owner",
    )
    
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
