"""Load and validate the local legal-document manifest (Phase 1 / Phase 10).

``manifest.json`` is the source of truth for local documents, so it is
validated before ingestion: required fields, unique ``doc_id``, ISO dates and
a known ``ocr_status``. Chroma is only an index and is never trusted for
metadata completeness.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

# ``done`` is what the manual-text import writes; the other values come from
# the plan's ocr_status contract.
OCR_STATUSES = {"text_layer", "ocr", "done", "missing_pdf", "failed"}

REQUIRED_DOC_FIELDS = (
    "doc_id",
    "portal_id",
    "title",
    "doc_type",
    "issuer",
    "issued_date",
    "ocr_status",
    "citation_label",
)

# Fields that must be non-empty when ocr_status says text exists.
TEXT_FIELDS_BY_STATUS = {
    "text_layer": "text_path",
    "ocr": "text_path",
    "done": "text_path",
}


class ManifestError(ValueError):
    """Raised when the manifest fails validation."""


def _is_iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def validate_manifest(data: Any) -> List[str]:
    """Return a list of validation errors (empty when the manifest is valid)."""
    errors: List[str] = []

    if not isinstance(data, dict):
        return ["manifest must be a JSON object"]

    locality = data.get("locality")
    if not isinstance(locality, dict):
        errors.append("missing locality object")
    else:
        if not str(locality.get("code") or "").strip():
            errors.append("locality.code is required")
        if not str(locality.get("name") or "").strip():
            errors.append("locality.name is required")

    documents = data.get("documents")
    if not isinstance(documents, list) or not documents:
        errors.append("documents must be a non-empty list")
        return errors

    seen: set = set()
    for index, doc in enumerate(documents):
        prefix = f"documents[{index}]"
        if not isinstance(doc, dict):
            errors.append(f"{prefix}: must be an object")
            continue

        doc_id = doc.get("doc_id")
        if not isinstance(doc_id, str) or not doc_id.strip():
            errors.append(f"{prefix}: doc_id is required")
        elif doc_id in seen:
            errors.append(f"{prefix}: duplicate doc_id {doc_id!r}")
        else:
            seen.add(doc_id)

        for field in REQUIRED_DOC_FIELDS:
            value = doc.get(field)
            if field == "portal_id":
                if value is None or value == "":
                    errors.append(f"{prefix}: portal_id is required")
            elif field == "issued_date":
                if not _is_iso_date(value):
                    errors.append(
                        f"{prefix}: issued_date must be YYYY-MM-DD, got {value!r}"
                    )
            elif field == "ocr_status":
                if value not in OCR_STATUSES:
                    errors.append(
                        f"{prefix}: ocr_status {value!r} not in {sorted(OCR_STATUSES)}"
                    )
            elif value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f"{prefix}: {field} is required")

        effective = doc.get("effective_date")
        if effective not in (None, "") and not _is_iso_date(effective):
            errors.append(
                f"{prefix}: effective_date must be YYYY-MM-DD, got {effective!r}"
            )

        status = doc.get("ocr_status")
        text_field = TEXT_FIELDS_BY_STATUS.get(str(status))
        if text_field and not str(doc.get(text_field) or "").strip():
            errors.append(f"{prefix}: {text_field} required for ocr_status={status!r}")

    return errors


def load_manifest(path: str | Path) -> Dict[str, Any]:
    """Load ``manifest.json`` and raise :class:`ManifestError` when invalid."""
    manifest_path = Path(path)
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(f"manifest not found: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest is not valid JSON: {exc}") from exc

    errors = validate_manifest(data)
    if errors:
        raise ManifestError(
            f"invalid manifest ({len(errors)} error(s)): " + "; ".join(errors[:5])
        )
    return data
