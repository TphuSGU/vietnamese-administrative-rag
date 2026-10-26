"""Unit tests for OCR fallback in DocumentLoader.

The real tesseract binary is optional in CI; these tests inject a fake
pytesseract module so the fallback wiring is verified without system packages.
"""

import io

import fitz
import pytest
from PIL import Image as PILImage

from app.models.exceptions import ExtractionError
from app.rag.ingestion import loader as loader_module
from app.rag.ingestion.loader import DocumentLoader


def _make_image_only_pdf(path, pages=1):
    """Create a PDF whose pages contain only an image (no text layer)."""
    image = PILImage.new("RGB", (600, 200), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    document = fitz.open()
    for _ in range(pages):
        page = document.new_page(width=600, height=200)
        page.insert_image(fitz.Rect(0, 0, 600, 200), stream=buffer.getvalue())
    document.save(path)
    document.close()


class _FakePytesseract:
    calls = 0

    @classmethod
    def image_to_string(cls, image, lang=None):
        cls.calls += 1
        return "Điều 1. Nội dung được nhận dạng từ ảnh scan."


class TestOCRFallback:
    def test_image_only_pdf_uses_ocr(self, tmp_path, monkeypatch):
        pdf_path = tmp_path / "scan.pdf"
        _make_image_only_pdf(pdf_path)

        monkeypatch.setattr(loader_module, "pytesseract", _FakePytesseract)
        loader = DocumentLoader(ocr_enabled=True, ocr_min_chars_per_page=10)
        loader._tesseract_available = True

        document = loader.load_document(file_path=str(pdf_path))

        assert "Nội dung được nhận dạng" in document.text
        assert _FakePytesseract.calls == 1

    def test_ocr_disabled_keeps_original_error(self, tmp_path):
        pdf_path = tmp_path / "scan.pdf"
        _make_image_only_pdf(pdf_path)

        loader = DocumentLoader(ocr_enabled=False)
        with pytest.raises(ExtractionError, match="No text content extracted"):
            loader.load_document(file_path=str(pdf_path))

    def test_missing_tesseract_keeps_original_error(self, tmp_path, monkeypatch):
        pdf_path = tmp_path / "scan.pdf"
        _make_image_only_pdf(pdf_path)

        monkeypatch.setattr(loader_module, "pytesseract", _FakePytesseract)
        loader = DocumentLoader(ocr_enabled=True)
        loader._tesseract_available = False

        with pytest.raises(ExtractionError, match="No text content extracted"):
            loader.load_document(file_path=str(pdf_path))

    def test_ocr_failure_does_not_drop_text_pages(self, tmp_path, monkeypatch):
        """A failing OCR page must not discard text extracted from other pages."""
        pdf_path = tmp_path / "mixed.pdf"
        document = fitz.open()
        page_one = document.new_page()
        page_one.insert_text((72, 72), "Dieu 1. Text layer co san.")
        page_two = document.new_page()
        image = PILImage.new("RGB", (600, 200), "white")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        page_two.insert_image(fitz.Rect(0, 0, 600, 200), stream=buffer.getvalue())
        document.save(pdf_path)
        document.close()

        class _FailingPytesseract:
            @staticmethod
            def image_to_string(image, lang=None):
                raise RuntimeError("tesseract exploded")

        monkeypatch.setattr(loader_module, "pytesseract", _FailingPytesseract)
        loader = DocumentLoader(ocr_enabled=True, ocr_min_chars_per_page=10)
        loader._tesseract_available = True

        loaded = loader.load_document(file_path=str(pdf_path))
        assert "Text layer co san" in loaded.text
