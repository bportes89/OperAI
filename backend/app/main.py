from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import router
from app.core.config import get_settings
app=FastAPI(title="OperAI API",version="0.1.0",docs_url="/docs")
app.add_middleware(CORSMiddleware,allow_origins=get_settings().cors_origins,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.include_router(router)
