from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession,async_sessionmaker,create_async_engine
from app.core.config import get_settings

engine=create_async_engine(get_settings().database_url,pool_pre_ping=True)
SessionLocal=async_sessionmaker(engine,expire_on_commit=False)

# Factory para criar sessões assíncronas em background tasks (ex: scheduler)
# Uso: async with async_session_maker() as session: ...
class async_session_maker:
    """Context manager para criar sessões de banco de dados em background tasks."""
    
    async def __aenter__(self):
        self.session = SessionLocal()
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

async def get_session()->AsyncIterator[AsyncSession]:
    async with SessionLocal() as session: yield session
