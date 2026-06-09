"""Aggregated catalog router."""
from fastapi import APIRouter

from apps.salon.domain.catalog.routers import organizations, professionals, services

router = APIRouter(prefix="/organizations", tags=["Organizations"])
router.include_router(organizations.router)
router.include_router(services.router)
router.include_router(professionals.router)
