from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.database import init_db
from app.core.config import FRONTEND_CORS_ORIGIN

# Import your cleanly separated routers
from app.routers import webhooks, workspace, jira, chat

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="VibeCoder Core Runtime API", lifespan=lifespan)

# Setup CORS using environment variables
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_CORS_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

# Include all the modular routers
app.include_router(webhooks.router)
app.include_router(workspace.router)
app.include_router(jira.router)
app.include_router(chat.router)