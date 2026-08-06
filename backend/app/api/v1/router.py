from fastapi import APIRouter

from app.api.v1 import auth, chat, conversations, filters, health, ingestion, search

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(search.router)
api_router.include_router(chat.router)
api_router.include_router(filters.router)
api_router.include_router(ingestion.router)
api_router.include_router(conversations.router)
api_router.include_router(auth.router)
