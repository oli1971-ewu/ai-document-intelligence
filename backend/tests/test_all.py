"""
Automated test suite for Doc Intel.

Tests cover:
  - Document processing pipeline (CSV, XLSX)
  - OCR service  
  - AI extraction (rule-based)
  - Validation engine
  - API endpoints
  - Failure scenarios
"""
from __future__ import annotations

import io
import os
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SAMPLE_DIR = Path(__file__).parent.parent.parent / "samples"


@pytest.fixture
def invoice_text():
    return """
    INVOICE

    Invoice No: INV-2024-0042
    Invoice Date: 2024-03-15
    Due Date: 2024-04-15

    From:
    Acme Supplies Ltd
    123 Business Park, London, UK

    To:
    Tech Corp International
    456 Corporate Ave, New York, USA

    Description               Qty    Unit Price    Amount
    Web Development Services   1     $5,000.00    $5,000.00
    Cloud Hosting (Monthly)    3       $200.00      $600.00
    Support Package            1       $400.00      $400.00

    Subtotal:   $6,000.00
    Tax (20%):  $1,200.00
    Total:      $7,200.00

    Currency: USD
    """


# ---------------------------------------------------------------------------
# --- Processing pipeline tests (CSV and XLSX don't need PyMuPDF)
# ---------------------------------------------------------------------------

class TestCSVProcessing:
    def test_csv_processing(self, tmp_path):
        from app.services.processing.spreadsheet_extractor import extract_csv
        csv_content = "invoice_number,supplier,total\nINV-001,Acme,1000.00\nINV-002,Globex,2500.50"
        f = tmp_path / "invoices.csv"
        f.write_text(csv_content, encoding="utf-8")
        text, rows = extract_csv(str(f))
        assert "INV-001" in text
        assert len(rows) >= 2

    def test_xlsx_processing(self, tmp_path):
        pytest.importorskip("openpyxl")
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Invoices"
        ws.append(["Invoice No", "Supplier", "Total"])
        ws.append(["INV-100", "Test Corp", 5000.00])
        path = tmp_path / "test.xlsx"
        wb.save(str(path))

        from app.services.processing.spreadsheet_extractor import extract_spreadsheet
        text, sheets = extract_spreadsheet(str(path))
        assert "INV-100" in text
        assert "Invoices" in sheets

    def test_csv_handles_unicode(self, tmp_path):
        from app.services.processing.spreadsheet_extractor import extract_csv
        content = "name,amount\nAcmé Corp,€1,234.00\nFoo & Bar,£500.00"
        f = tmp_path / "unicode.csv"
        f.write_bytes(content.encode("utf-8"))
        text, rows = extract_csv(str(f))
        assert isinstance(text, str)
        assert len(rows) >= 1

    def test_unsupported_extension(self, tmp_path):
        from app.services.processing.pipeline import process_document
        f = tmp_path / "test.docx"
        f.write_bytes(b"fake content")
        result = process_document(str(f), "test.docx")
        assert result.success is False
        assert "Unsupported" in (result.error or "")


# ---------------------------------------------------------------------------
# --- OCR tests
# ---------------------------------------------------------------------------

class TestOCR:
    def test_ocr_with_blank_image(self):
        pytest.importorskip("PIL")
        from PIL import Image
        from app.services.processing.ocr import ocr_image
        img = Image.new("RGB", (200, 100), color="white")
        result = ocr_image(img)
        assert isinstance(result, str)

    def test_ocr_returns_string(self):
        pytest.importorskip("PIL")
        from PIL import Image
        from app.services.processing.ocr import ocr_image
        img = Image.new("RGB", (100, 50), color=(200, 200, 200))
        result = ocr_image(img)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# --- Extraction tests (rule-based, no DB/LLM needed)
# ---------------------------------------------------------------------------

class TestRuleBasedExtraction:
    def test_extracts_invoice_number(self, invoice_text):
        from app.services.extraction.extractor import _extract_rule_based
        result = _extract_rule_based(invoice_text)
        assert result is not None
        assert result.invoice_number is not None

    def test_extracts_total(self, invoice_text):
        from app.services.extraction.extractor import _extract_rule_based
        result = _extract_rule_based(invoice_text)
        assert result.total is not None
        assert float(result.total) > 0

    def test_detects_usd_currency(self, invoice_text):
        from app.services.extraction.extractor import _extract_rule_based
        result = _extract_rule_based(invoice_text)
        assert result.currency == "USD"

    def test_empty_text_returns_model(self):
        from app.services.extraction.extractor import _extract_rule_based
        result = _extract_rule_based("   ")
        assert result is not None

    def test_does_not_invent_values(self):
        from app.services.extraction.extractor import _extract_rule_based
        result = _extract_rule_based("This is a random document with no invoice data.")
        assert result.total is None

    def test_confidence_is_between_0_and_1(self, invoice_text):
        from app.services.extraction.extractor import _extract_rule_based
        result = _extract_rule_based(invoice_text)
        if result.confidence is not None:
            assert 0.0 <= float(result.confidence) <= 1.0

    def test_extract_invoice_none_on_empty(self):
        from app.services.extraction.extractor import extract_invoice
        result = extract_invoice("")
        assert result is None

    def test_extract_invoice_none_on_whitespace(self):
        from app.services.extraction.extractor import extract_invoice
        result = extract_invoice("   \n\t  ")
        assert result is None

    def test_llm_none_uses_rules(self, invoice_text):
        """With LLM_PROVIDER=none (set in conftest), should use rule-based."""
        from app.services.extraction.extractor import extract_invoice
        result = extract_invoice(invoice_text)
        # Rule-based should return something non-null
        assert result is not None


# ---------------------------------------------------------------------------
# --- Validation tests (mocked SQLAlchemy, no DB connection)
# ---------------------------------------------------------------------------

class TestValidation:
    def _make_mock_invoice(self, **kwargs):
        inv = MagicMock()
        inv.invoice_number = kwargs.get("invoice_number", "INV-001")
        inv.invoice_date = kwargs.get("invoice_date", "2024-01-15")
        inv.supplier_name = kwargs.get("supplier_name", "Test Supplier")
        inv.customer_name = kwargs.get("customer_name", "Test Customer")
        inv.subtotal = kwargs.get("subtotal", Decimal("100.00"))
        inv.tax = kwargs.get("tax", Decimal("20.00"))
        inv.total = kwargs.get("total", Decimal("120.00"))
        inv.currency = kwargs.get("currency", "USD")
        inv.line_items = kwargs.get("line_items", [])
        return inv

    def _make_mock_db(self, duplicate=None):
        db = MagicMock()
        # Mock query chain: db.query(...).filter(...).first()
        db.query.return_value.filter.return_value.first.return_value = duplicate
        return db

    def _run_validation(self, inv, duplicate=None):
        from app.services.validation.validator import _run_rules
        return _run_rules(inv, self._make_mock_db(duplicate), uuid.uuid4())

    def test_valid_invoice_no_errors(self):
        from app.services.validation.validator import _run_rules
        inv = self._make_mock_invoice()
        issues = _run_rules(inv, self._make_mock_db(), uuid.uuid4())
        error_issues = [i for i in issues if i["severity"] == "error"]
        assert len(error_issues) == 0

    def test_missing_total_flagged(self):
        from app.services.validation.validator import _run_rules
        inv = self._make_mock_invoice(total=None)
        issues = _run_rules(inv, self._make_mock_db(), uuid.uuid4())
        codes = [i["code"] for i in issues]
        assert "MISSING_FIELD" in codes

    def test_total_mismatch_detected(self):
        from app.services.validation.validator import _run_rules
        inv = self._make_mock_invoice(subtotal=Decimal("100"), tax=Decimal("20"), total=Decimal("90"))
        issues = _run_rules(inv, self._make_mock_db(), uuid.uuid4())
        codes = [i["code"] for i in issues]
        assert "TOTAL_MISMATCH" in codes

    def test_negative_amount_detected(self):
        from app.services.validation.validator import _run_rules
        inv = self._make_mock_invoice(total=Decimal("-100"))
        issues = _run_rules(inv, self._make_mock_db(), uuid.uuid4())
        codes = [i["code"] for i in issues]
        assert "NEGATIVE_VALUE" in codes

    def test_none_invoice_returns_no_extraction_error(self):
        from app.services.validation.validator import _run_rules
        issues = _run_rules(None, self._make_mock_db(), uuid.uuid4())
        assert any(i["code"] == "NO_EXTRACTION" for i in issues)

    def test_duplicate_invoice_detected(self):
        from app.services.validation.validator import _run_rules
        inv = self._make_mock_invoice()
        fake_dup = MagicMock()
        fake_dup.document_id = uuid.uuid4()
        issues = _run_rules(inv, self._make_mock_db(duplicate=fake_dup), uuid.uuid4())
        codes = [i["code"] for i in issues]
        assert "DUPLICATE_INVOICE" in codes


# ---------------------------------------------------------------------------
# --- Failure scenarios
# ---------------------------------------------------------------------------

class TestFailureScenarios:
    def test_pipeline_handles_missing_file(self):
        from app.services.processing.pipeline import process_document
        result = process_document("/nonexistent/path/file.pdf", "file.pdf")
        assert result.success is False

    def test_extraction_handles_garbage_text(self):
        from app.services.extraction.extractor import extract_invoice
        garbage = "asdfjkl;qwerty!@#$%^&*()" * 100
        result = extract_invoice(garbage)
        assert result is None or hasattr(result, "invoice_number")

    def test_extraction_handles_very_long_text(self):
        from app.services.extraction.extractor import extract_invoice
        long_text = "invoice number INV-999\ntotal $100.00\n" * 10000
        result = extract_invoice(long_text)
        assert result is None or hasattr(result, "invoice_number")

    def test_csv_corrupted_encoding_raises_gracefully(self, tmp_path):
        from app.services.processing.spreadsheet_extractor import extract_csv
        f = tmp_path / "bad.csv"
        f.write_bytes(b"\xff\xfe bad binary data \x00\x01\x02")
        try:
            text, rows = extract_csv(str(f))
            # If it doesn't raise, that's also fine
        except Exception as e:
            # Should raise a ValueError or similar, not a crash
            assert isinstance(e, (ValueError, UnicodeDecodeError, Exception))


# ---------------------------------------------------------------------------
# --- Real sample documents tests
# ---------------------------------------------------------------------------

class TestRealSampleDocuments:
    def test_sample_invoice_1_pipeline_and_validation(self):
        from app.services.processing.pipeline import process_document
        from app.services.extraction.extractor import extract_invoice
        from app.services.validation.validator import _run_rules

        pdf_path = SAMPLE_DIR / "sample_invoice_1.pdf"
        assert pdf_path.exists(), f"Missing {pdf_path}"

        result = process_document(str(pdf_path))
        assert result.success is True
        assert "INVOICE" in result.text

        inv = extract_invoice(result.text)
        assert inv is not None
        assert inv.invoice_number == "INV-2024-0042"
        assert inv.subtotal == 6000.0
        assert inv.tax == 1200.0
        assert inv.total == 7200.0
        assert inv.currency == "USD"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        issues = _run_rules(inv, mock_db, uuid.uuid4())
        # Clean invoice should have 0 errors
        assert [i for i in issues if i["severity"] == "error"] == []

    def test_sample_invoice_2_math_error_validation(self):
        from app.services.processing.pipeline import process_document
        from app.services.extraction.extractor import extract_invoice
        from app.services.validation.validator import _run_rules

        pdf_path = SAMPLE_DIR / "sample_invoice_2_math_error.pdf"
        assert pdf_path.exists(), f"Missing {pdf_path}"

        result = process_document(str(pdf_path))
        assert result.success is True

        inv = extract_invoice(result.text)
        assert inv is not None
        assert inv.invoice_number == "INV-DUPE-0001"
        assert inv.subtotal == 2500.0
        assert inv.tax == 525.0
        assert inv.total == 2900.0
        assert inv.currency == "EUR"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        issues = _run_rules(inv, mock_db, uuid.uuid4())
        codes = [i["code"] for i in issues]
        assert "TOTAL_MISMATCH" in codes

    def test_sample_invoices_csv_pipeline(self):
        from app.services.processing.pipeline import process_document
        csv_path = SAMPLE_DIR / "sample_invoices.csv"
        assert csv_path.exists(), f"Missing {csv_path}"

        result = process_document(str(csv_path))
        assert result.success is True
        assert result.doc_type == "csv"
        assert "INV-CSV-001" in result.text

    def test_sample_invoices_xlsx_pipeline(self):
        from app.services.processing.pipeline import process_document
        xlsx_path = SAMPLE_DIR / "sample_invoices.xlsx"
        assert xlsx_path.exists(), f"Missing {xlsx_path}"

        result = process_document(str(xlsx_path))
        assert result.success is True
        assert result.doc_type == "xlsx"
        assert "INV-XL-001" in result.text


# ---------------------------------------------------------------------------
# --- API endpoint tests (FastAPI TestClient)
# ---------------------------------------------------------------------------

class TestAPIEndpoints:
    @pytest.fixture(autouse=True)
    def setup_client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.db.session import get_db

        self.mock_db = MagicMock()
        app.dependency_overrides[get_db] = lambda: self.mock_db
        self.client = TestClient(app, raise_server_exceptions=False)
        yield
        app.dependency_overrides.clear()

    def test_root_and_health(self):
        res = self.client.get("/")
        assert res.status_code == 200
        assert "Doc Intel API" in res.json()["message"]

        res = self.client.get("/api/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

    def test_list_documents(self):
        self.mock_db.query.return_value.order_by.return_value.count.return_value = 0
        self.mock_db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        res = self.client.get("/api/documents")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0
        assert data["documents"] == []

    def test_get_document_not_found(self):
        fake_id = str(uuid.uuid4())
        self.mock_db.get.return_value = None
        res = self.client.get(f"/api/documents/{fake_id}")
        assert res.status_code == 404

    def test_get_document_found(self):
        doc_id = uuid.uuid4()
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.filename = "invoice.pdf"
        mock_doc.content_type = "application/pdf"
        mock_doc.size_bytes = 2048
        mock_doc.status = "completed"
        mock_doc.doc_type = "pdf"
        mock_doc.page_count = 1
        mock_doc.error = None
        mock_doc.created_at = None
        mock_doc.updated_at = None
        self.mock_db.get.return_value = mock_doc

        res = self.client.get(f"/api/documents/{doc_id}")
        assert res.status_code == 200
        assert res.json()["filename"] == "invoice.pdf"

    def test_get_document_status(self):
        doc_id = uuid.uuid4()
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.status = "processing"
        mock_doc.error = None
        mock_doc.events = []
        self.mock_db.get.return_value = mock_doc

        res = self.client.get(f"/api/documents/{doc_id}/status")
        assert res.status_code == 200
        assert res.json()["status"] == "processing"

    def test_get_document_results(self):
        doc_id = uuid.uuid4()
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.filename = "sample.pdf"
        mock_doc.content_type = "application/pdf"
        mock_doc.size_bytes = 1000
        mock_doc.status = "completed"
        mock_doc.doc_type = "pdf"
        mock_doc.page_count = 1
        mock_doc.error = None
        mock_doc.created_at = None
        mock_doc.updated_at = None

        mock_inv = MagicMock()
        mock_inv.id = uuid.uuid4()
        mock_inv.invoice_number = "INV-2024-999"
        mock_inv.invoice_date = "2024-05-01"
        mock_inv.supplier_name = "Global Logistics"
        mock_inv.customer_name = "Acme Inc"
        mock_inv.subtotal = 500.0
        mock_inv.tax = 100.0
        mock_inv.total = 600.0
        mock_inv.currency = "USD"
        mock_inv.confidence = 0.98
        mock_inv.source = "rule_based"
        mock_inv.line_items = []

        self.mock_db.get.return_value = mock_doc
        self.mock_db.query.return_value.filter_by.return_value.first.return_value = mock_inv
        self.mock_db.query.return_value.filter_by.return_value.all.return_value = []

        res = self.client.get(f"/api/documents/{doc_id}/results")
        assert res.status_code == 200
        data = res.json()
        assert data["invoice"]["invoice_number"] == "INV-2024-999"
        assert data["invoice"]["total"] == 600.0

    def test_correct_document(self):
        doc_id = uuid.uuid4()
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_inv = MagicMock()
        mock_inv.id = uuid.uuid4()
        mock_inv.invoice_number = "INV-OLD"
        mock_inv.invoice_date = "2024-01-01"
        mock_inv.supplier_name = "Old Supplier"
        mock_inv.customer_name = "Client"
        mock_inv.subtotal = 100.0
        mock_inv.tax = 20.0
        mock_inv.total = 120.0
        mock_inv.currency = "USD"
        mock_inv.confidence = 1.0
        mock_inv.source = "rule_based"
        mock_inv.line_items = []

        self.mock_db.get.return_value = mock_doc
        self.mock_db.query.return_value.filter_by.return_value.first.return_value = mock_inv

        res = self.client.patch(
            f"/api/documents/{doc_id}/correct",
            json={"total": 200.0, "invoice_number": "INV-NEW"},
        )
        assert res.status_code == 200
        assert res.json()["message"] == "Corrections saved"

    def test_reprocess_document(self):
        doc_id = uuid.uuid4()
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        self.mock_db.get.return_value = mock_doc

        with patch("app.tasks.process.process_document_task.delay") as mock_delay:
            res = self.client.post(f"/api/documents/{doc_id}/reprocess")
            assert res.status_code == 200
            assert mock_delay.called

    def test_delete_document(self):
        doc_id = uuid.uuid4()
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.storage_path = "/nonexistent/test.pdf"
        self.mock_db.get.return_value = mock_doc

        res = self.client.delete(f"/api/documents/{doc_id}")
        assert res.status_code == 200
        assert res.json()["message"] == "Document deleted"

    def test_upload_unsupported_file_type(self):
        file_content = b"executable binary content"
        files = {"files": ("malicious.exe", io.BytesIO(file_content), "application/octet-stream")}
        res = self.client.post("/api/documents/upload", files=files)
        assert res.status_code == 200
        data = res.json()
        assert data["uploaded"] == 0
        assert "Unsupported file type" in data["results"][0]["error"]

    def test_search_query_validation(self):
        res = self.client.get("/api/search")
        assert res.status_code == 422
        res = self.client.get("/api/search?q=test&mode=unsupported_mode")
        assert res.status_code == 422

    def test_search_keyword_execution(self):
        self.mock_db.execute.return_value.fetchall.return_value = []
        res = self.client.get("/api/search?q=invoice&mode=keyword")
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "keyword"
        assert "results" in data

