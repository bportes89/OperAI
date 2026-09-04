from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession,async_sessionmaker,create_async_engine
from app.core.config import get_settings

engine=create_async_engine(get_settings().database_url,pool_pre_ping=True)
SessionLocal=async_sessionmaker(engine,expire_on_commit=False)

# Criador de sessões assíncronas para uso em background tasks
class AsyncSessionMaker:
    """Context manager para criar sessões de banco de dados em background tasks."""
    
    def __call__(self):
        """Permite usar async_session_maker() como um factory."""
        return self
    
    async def __aenter__(self):
        self.session = SessionLocal()
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

# Exporta o criador de sessões para uso em tasks
async_session_maker = AsyncSessionMaker()

async def get_session()->AsyncIterator[AsyncSession]:
    async with SessionLocal() as session: yield session
