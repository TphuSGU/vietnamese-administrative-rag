"""Phase 9: locality reference endpoints (profile / procedures / documents).

File-backed demo API — must stay public (no auth), URL-free, and filterable
by accent-insensitive `q`.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_profile_endpoint_returns_an_phu_profile():
    response = client.get("/api/v1/localities/an-phu/profile")

    assert response.status_code == 200
    body = response.json()
    assert body["locality"]["code"] == "25975"
    assert body["locality"]["name"] == "Phường An Phú"
    assert body["contact"]["phone"]
    assert body["working_hours"]["weekdays"].startswith("07:30")
    assert len(body["schedules"]) == 18
    assert body["verification"]["dvc_ward_code"] == "25975"
    # Không URL nào được lộ ra API (kể cả portal/source_url)
    assert "http://" not in response.text.lower()
    assert "https://" not in response.text.lower()


def test_profile_schedule_items_have_no_url_fields():
    body = client.get("/api/v1/localities/an-phu/profile").json()
    for schedule in body["schedules"]:
        assert set(schedule) == {"schedule_id", "title", "published_at"}


def test_procedures_list_defaults_to_an_phu():
    response = client.get("/api/v1/procedures", params={"limit": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1506
    assert body["locality_code"] == "25975"
    assert len(body["items"]) == 5
    item = body["items"][0]
    assert item["procedure_id"]
    assert item["name"]
    # source_url/text/raw path không được xuất hiện
    assert "source_url" not in item
    assert "http" not in response.text.lower()


def test_procedures_q_filter_is_accent_insensitive():
    with_accents = client.get("/api/v1/procedures", params={"q": "hộ tịch"}).json()
    without_accents = client.get("/api/v1/procedures", params={"q": "ho tich"}).json()

    assert with_accents["total"] > 0
    assert with_accents["total"] == without_accents["total"]


def test_procedures_unknown_locality_returns_empty():
    body = client.get("/api/v1/procedures", params={"locality_code": "99999"}).json()
    assert body["total"] == 0
    assert body["items"] == []


def test_procedures_offset_beyond_total_returns_empty_page():
    body = client.get(
        "/api/v1/procedures", params={"limit": 5, "offset": 100000}
    ).json()
    assert body["total"] == 1506
    assert body["items"] == []


def test_legal_documents_list_from_manifest():
    response = client.get("/api/v1/legal-documents", params={"limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 52
    assert len(body["items"]) == 10
    item = body["items"][0]
    assert item["doc_id"].startswith("an_phu_")
    assert item["doc_scope"] == "local"
    assert "pdf_url" not in item and "source_url" not in item
    assert "http" not in response.text.lower()


def test_legal_documents_q_filter_matches_title_or_number():
    body = client.get(
        "/api/v1/legal-documents", params={"q": "nghị quyết"}
    ).json()
    assert 0 < body["total"] < 52


def test_reference_routes_registered_for_openapi():
    paths = {route.path for route in app.routes}
    assert "/api/v1/localities/an-phu/profile" in paths
    assert "/api/v1/procedures" in paths
    assert "/api/v1/legal-documents" in paths
