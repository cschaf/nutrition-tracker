# src/app/domain/ports.py
from abc import ABC, abstractmethod

from app.domain.models import GeneralizedProduct


class ProductSourcePort(ABC):
    """
    Abstrakte Schnittstelle für externe Produktdatenquellen.
    Jeder Adapter MUSS dieses Interface implementieren.
    Die Core-Domain kennt ausschließlich dieses Interface.
    """

    @abstractmethod
    async def fetch_by_id(self, product_id: str) -> GeneralizedProduct:
        """
        Ruft ein Produkt anhand seiner source-spezifischen ID ab
        und gibt ein normalisiertes GeneralizedProduct zurück.

        Raises:
            ProductNotFoundError: Wenn das Produkt nicht gefunden wurde.
            ExternalApiError: Bei Kommunikationsproblemen mit der externen API.
        """
        ...

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[GeneralizedProduct]:
        """Sucht nach Produkten anhand eines Suchbegriffs."""
        ...


# ---------------------------------------------------------------------------
# Custom Domain Exceptions
# ---------------------------------------------------------------------------


class ProductNotFoundError(Exception):
    def __init__(self, product_id: str, source: str):
        super().__init__(f"Product '{product_id}' not found in source '{source}'")
        self.product_id = product_id
        self.source = source


class ExternalApiError(Exception):
    def __init__(self, source: str, detail: str):
        super().__init__(f"External API error from '{source}': {detail}")
        self.source = source
        self.detail = detail
