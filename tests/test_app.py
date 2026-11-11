"""Tests run with SQLite, so CI does not require a PostgreSQL server."""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Parcel  # noqa: E402


def test_health_and_metrics():
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok", "database": "connected"}
        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "parcelops_http_requests_total" in metrics.text


def test_register_and_update_parcel():
    with TestClient(app) as client:
        with SessionLocal() as db:
            db.execute(delete(Parcel))
            db.commit()
        response = client.post(
            "/parcels", data={"parcel_id": "PAR-001", "locality": "Agbarho"}, follow_redirects=False
        )
        assert response.status_code == 303
        assert "PAR-001" in client.get("/").text
        with SessionLocal() as db:
            parcel = db.query(Parcel).filter_by(parcel_id="PAR-001").one()
            pk = parcel.id
        result = client.post(f"/parcels/{pk}/status", data={"new_status": "Validated"}, follow_redirects=False)
        assert result.status_code == 303
        with SessionLocal() as db:
            assert db.get(Parcel, pk).status == "Validated"
        duplicate = client.post("/parcels", data={"parcel_id": "PAR-001", "locality": "Agbarho"}, follow_redirects=False)
        assert duplicate.status_code == 303
        assert "error=duplicate" in duplicate.headers["location"]
        invalid = client.post(f"/parcels/{pk}/status", data={"new_status": "Approved"})
        assert invalid.status_code == 422
