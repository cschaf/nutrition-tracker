from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.security import get_tenant_id
from app.main import app


def test_export_logs_csv_success(client: TestClient, alice_headers: dict[str, str]) -> None:
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_alice"

    with patch(
        "app.repositories.sqlite_log_repository.SQLiteLogRepository.find_by_date_range",
        new_callable=AsyncMock,
    ) as mock_find:
        mock_find.return_value = []

        try:
            response = client.get(
                "/api/v1/logs/export/csv",
                params={"from": "2024-05-01", "to": "2024-05-31"},
                headers=alice_headers,
            )
            assert response.status_code == 200
            assert response.headers["Content-Type"] == "text/csv; charset=utf-8"
            assert (
                'attachment; filename="nutrition_2024-05-01_2024-05-31.csv"'
                in response.headers["Content-Disposition"]
            )
            # Check if header is present in the body
            assert "date,time,product_name" in response.text
        finally:
            app.dependency_overrides.clear()


def test_export_logs_csv_validation_error(
    client: TestClient, alice_headers: dict[str, str]
) -> None:
    app.dependency_overrides[get_tenant_id] = lambda: "tenant_alice"
    try:
        # 'to' before 'from'
        response = client.get(
            "/api/v1/logs/export/csv",
            params={"from": "2024-05-31", "to": "2024-05-01"},
            headers=alice_headers,
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()
