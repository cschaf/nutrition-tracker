# src/app/adapters/manual.py
from __future__ import annotations

from app.domain.models import DataSource, GeneralizedProduct
from app.domain.ports import ProductNotFoundError, ProductSourcePort
from app.repositories.manual_product_repository import ManualProductRepository


class ManualProductAdapter(ProductSourcePort):
    """
    Adapter for manually created products.
    """

    def __init__(self, repository: ManualProductRepository) -> None:
        self._repo = repository

    async def fetch_by_id(self, product_id: str) -> GeneralizedProduct:
        product = self._repo.find_by_id(product_id)
        if not product:
            raise ProductNotFoundError(product_id=product_id, source=DataSource.MANUAL)
        return product

    async def search(self, query: str, limit: int = 10) -> list[GeneralizedProduct]:
        return self._repo.search(query, limit)
