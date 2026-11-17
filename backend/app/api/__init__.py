"""API router — mounts all sub-routers."""
from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.admin_docs import router as docs_router
from app.api.admin_history import router as history_router
from app.api.admin_resolution import router as resolution_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(chat_router, prefix="/chat", tags=["chat"])
router.include_router(docs_router, prefix="/admin/documents", tags=["admin-documents"])
router.include_router(history_router, prefix="/admin/history", tags=["admin-history"])
router.include_router(resolution_router, prefix="/admin/resolution", tags=["admin-resolution"])
