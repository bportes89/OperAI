from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from app.api import router
from app.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia lifecycle da aplicação - startup e shutdown."""
    # Startup
    from app.scheduler import start_scheduler
    from app.websocket import manager
    
    # Inicia o agendador de tarefas
    start_scheduler(interval_minutes=5)
    
    yield
    
    # Shutdown
    from app.scheduler import stop_scheduler
    
    # Para o agendador
    stop_scheduler()


app = FastAPI(
    title="OperAI API",
    version="0.1.0",
    docs_url="/docs",
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


def _cors_headers(request: Request) -> dict[str, str]:
    origin = request.headers.get("origin", "")
    if origin and origin.rstrip("/") in {o.rstrip("/") for o in settings.cors_origins}:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers=_cors_headers(request),
    )
