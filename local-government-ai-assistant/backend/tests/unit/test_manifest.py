"""Manifest validator tests (Phase 10: đủ trường, không trùng, ngày hợp lệ)."""

import json
from pathlib import Path

import pytest

from app.rag.ingestion.manifest import (
    ManifestError,
    load_manifest,
    validate_manifest,
)


def make_manifest(**overrides):
    base = {
        "locality": {"code": "25975", "name": "Phường An Phú"},
        "documents": [
            {
                "doc_id": "an_phu_2788",
                "portal_id": 2788,
                "title": "Quy chế tiếp công dân của HĐND phường An Phú",
                "doc_type": "Nghị quyết",
                "issuer": "HĐND phường An Phú",
                "issued_date": "2026-07-29",
                "ocr_status": "done",
                "citation_label": (
                    "Nghị quyết số 25/NQ-HĐND ngày 29/7/2026 của HĐND phường An Phú"
                ),
                "text_path": "text/an_phu_2788.txt",
            }
        ],
    }
    base.update(overrides)
    return base


def test_valid_manifest_has_no_errors():
    assert validate_manifest(make_manifest()) == []


def test_manifest_requires_locality_code():
    data = make_manifest(locality={"name": "Phường An Phú"})
    errors = validate_manifest(data)
    assert any("locality.code" in error for error in errors)


def test_duplicate_doc_id_is_rejected():
    data = make_manifest()
    data["documents"].append(dict(data["documents"][0]))
    errors = validate_manifest(data)
    assert any("duplicate doc_id" in error for error in errors)


@pytest.mark.parametrize("bad_date", ["29/7/2026", "2026-13-40", "", None, 20260729])
def test_invalid_issued_date_is_rejected(bad_date):
    data = make_manifest()
    data["documents"][0]["issued_date"] = bad_date
    errors = validate_manifest(data)
    assert any("issued_date" in error for error in errors)


def test_unknown_ocr_status_is_rejected():
    data = make_manifest()
    data["documents"][0]["ocr_status"] = "pending"
    errors = validate_manifest(data)
    assert any("ocr_status" in error for error in errors)


def test_text_status_requires_text_path():
    data = make_manifest()
    data["documents"][0]["text_path"] = ""
    errors = validate_manifest(data)
    assert any("text_path" in error for error in errors)


def test_missing_pdf_status_does_not_require_text_path():
    data = make_manifest()
    data["documents"][0]["ocr_status"] = "missing_pdf"
    data["documents"][0].pop("text_path", None)
    assert validate_manifest(data) == []


def test_empty_documents_is_rejected():
    errors = validate_manifest(make_manifest(documents=[]))
    assert any("non-empty" in error for error in errors)


def test_load_manifest_raises_on_invalid_file(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"documents": []}), encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(path)


def test_load_manifest_roundtrip_valid_file(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(make_manifest()), encoding="utf-8")
    loaded = load_manifest(path)
    assert loaded["documents"][0]["doc_id"] == "an_phu_2788"


REAL_MANIFEST = Path("data/localities/an_phu/manifest.json")


@pytest.mark.skipif(not REAL_MANIFEST.exists(), reason="local An Phú data not present")
def test_real_an_phu_manifest_is_valid():
    """The shipped An Phú manifest must satisfy the validator."""
    errors = validate_manifest(json.loads(REAL_MANIFEST.read_text(encoding="utf-8")))
    assert errors == []
