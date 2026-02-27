from __future__ import annotations

import time

from app.domain.models import DataSource, GeneralizedProduct


class ProductCache:
    """
    Einfacher TTL-basierter In-Memory Cache für Produkte.
    Verhindert redundante externe API-Aufrufe.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        # Key: (DataSource, product_id), Value: (GeneralizedProduct, timestamp)
        self._storage: dict[tuple[DataSource, str], tuple[GeneralizedProduct, float]] = {}

    def get(self, source: DataSource, product_id: str) -> GeneralizedProduct | None:
        """Holt ein Produkt aus dem Cache, sofern vorhanden und nicht abgelaufen."""
        key = (source, product_id)
        if key not in self._storage:
            return None

        product, timestamp = self._storage[key]
        if (time.time() - timestamp) > self._ttl:
            del self._storage[key]
            return None

        return product

    def set(self, source: DataSource, product_id: str, product: GeneralizedProduct) -> None:
        """Speichert ein Produkt im Cache mit aktuellem Zeitstempel."""
        self._storage[(source, product_id)] = (product, time.time())
