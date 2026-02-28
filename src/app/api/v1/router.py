# src/app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1 import goals, logs, products, templates

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(logs.router)
api_router.include_router(products.router)
api_router.include_router(goals.router)
api_router.include_router(templates.router)
