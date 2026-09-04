from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession,async_sessionmaker,create_async_engine
from app.core.config import get_settings

engine=create_async_engine(get_settings().database_url,pool_pre_ping=True)
SessionLocal=async_sessionmaker(engine,expire_on_commit=False)

# Factory para criar sessões assíncronas em background tasks (ex: scheduler)
# Uso: async with async_session_maker() as session: ...
async def async_session_maker():
    """Factory que retorna uma nova sessão de banco de dados para uso em background tasks."""
    return SessionLocal()

async def get_session()->AsyncIterator[AsyncSession]:
    async with SessionLocal() as session: yield session
