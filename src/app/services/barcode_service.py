from __future__ import annotations

import logging

from app.domain.models import DataSource, GeneralizedProduct
from app.domain.ports import ProductNotFoundError, ProductSourcePort

logger = logging.getLogger(__name__)


class BarcodeService:
    """
    Service für den Barcode-Lookup über mehrere Datenquellen hinweg.
    Die Reihenfolge der Quellen wird über die Konfiguration gesteuert.
    """

    def __init__(
        self,
        adapter_registry: dict[DataSource, ProductSourcePort],
        lookup_order: list[str],
    ) -> None:
        self._adapter_registry = adapter_registry
        self._lookup_order = lookup_order

    async def lookup(self, barcode: str) -> GeneralizedProduct:
        """
        Sucht nach einem Produkt anhand des Barcodes in den konfigurierten Quellen.

        Raises:
            ProductNotFoundError: Wenn das Produkt in keiner Quelle gefunden wurde.
            ExternalApiError: Wenn bei einem Adapter ein Netzwerk- oder API-Fehler
                auftritt (propagiert).
        """
        for source_name in self._lookup_order:
            try:
                source_enum = DataSource(source_name)
            except ValueError:
                logger.warning("Invalid source '%s' in BARCODE_LOOKUP_ORDER", source_name)
                continue

            adapter = self._adapter_registry.get(source_enum)
            if not adapter:
                logger.warning("No adapter found for source '%s'", source_name)
                continue

            try:
                return await adapter.fetch_by_id(barcode)
            except ProductNotFoundError:
                continue

        raise ProductNotFoundError(barcode, "all_configured_sources")
