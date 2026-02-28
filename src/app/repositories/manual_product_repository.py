# src/app/repositories/manual_product_repository.py
from __future__ import annotations

from app.domain.models import GeneralizedProduct


class ManualProductRepository:
    """
    In-memory storage for manually created products.

    ADR: Manual Product Persistence
    Decision: We use an in-memory repository (Option A) for manual products.
    Reasoning: For a homelab/single-user environment, this is sufficient.
    Products are stored in a simple dictionary during runtime.
    Note: These products are currently global and not isolated by tenant_id,
    matching the behavior of external API products and the product cache.
    """

    def __init__(self) -> None:
        self._products: dict[str, GeneralizedProduct] = {}

    def save(self, product: GeneralizedProduct) -> None:
        self._products[product.id] = product

    def find_by_id(self, product_id: str) -> GeneralizedProduct | None:
        return self._products.get(product_id)

    def search(self, query: str, limit: int = 10) -> list[GeneralizedProduct]:
        query_lower = query.lower()
        results = [
            p
            for p in self._products.values()
            if query_lower in p.name.lower() or (p.brand and query_lower in p.brand.lower())
        ]
        return results[:limit]
