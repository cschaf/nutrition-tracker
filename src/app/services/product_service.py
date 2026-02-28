# src/app/services/product_service.py
from __future__ import annotations

import uuid

from app.domain.models import DataSource, GeneralizedProduct, ManualProductCreate
from app.repositories.manual_product_repository import ManualProductRepository


class ProductService:
    def __init__(self, manual_repo: ManualProductRepository) -> None:
        self._manual_repo = manual_repo

    def create_manual_product(self, payload: ManualProductCreate) -> GeneralizedProduct:
        product = GeneralizedProduct(
            id=str(uuid.uuid4()),
            source=DataSource.MANUAL,
            name=payload.name,
            brand=payload.brand,
            macronutrients=payload.macronutrients,
            micronutrients=payload.micronutrients,
            is_liquid=payload.is_liquid,
            volume_ml_per_100g=payload.volume_ml_per_100g,
        )
        self._manual_repo.save(product)
        return product
