# src/app/services/export_service.py
from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.models import LogEntry


class ExportService:
    def generate_csv(self, entries: list[LogEntry]) -> Iterator[str]:
        """
        Generiert CSV-Daten für eine Liste von LogEntries.
        Gibt einen Iterator zurück, der Zeile für Zeile als String liefert.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        header = [
            "date",
            "time",
            "product_name",
            "brand",
            "source",
            "quantity_g",
            "calories_kcal",
            "protein_g",
            "carbohydrates_g",
            "fat_g",
            "fiber_g",
            "sugar_g",
            "is_liquid",
            "volume_ml",
            "note",
        ]
        writer.writerow(header)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for entry in entries:
            macros = entry.scaled_macros
            row = [
                str(entry.log_date),
                entry.consumed_at.strftime("%H:%M:%S"),
                entry.product.name,
                entry.product.brand or "",
                entry.product.source,
                str(entry.quantity_g),
                str(macros.calories_kcal),
                str(macros.protein_g),
                str(macros.carbohydrates_g),
                str(macros.fat_g),
                str(macros.fiber_g) if macros.fiber_g is not None else "",
                str(macros.sugar_g) if macros.sugar_g is not None else "",
                "true" if entry.product.is_liquid else "false",
                str(entry.consumed_volume_ml) if entry.consumed_volume_ml is not None else "",
                entry.note or "",
            ]
            writer.writerow(row)
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)
