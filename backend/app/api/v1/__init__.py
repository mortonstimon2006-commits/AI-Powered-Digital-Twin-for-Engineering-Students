from fastapi import APIRouter

from app.api.v1 import admin, auth, career, documents, health, mentor, planning, privacy, staff, twin

api_router = APIRouter()
for module in (health, auth, twin, career, planning, mentor, documents, privacy, staff, admin):
    api_router.include_router(module.router)
