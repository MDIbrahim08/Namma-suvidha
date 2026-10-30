"""Aggregates all v1 routers. Mounted under API_V1_PREFIX in main.py."""

from fastapi import APIRouter

from app.api.v1 import citizen, evaluator, government, health
from app.modules.discovery.router import router as discovery_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(citizen.router)
api_router.include_router(discovery_router)
api_router.include_router(evaluator.router)
api_router.include_router(government.router)

