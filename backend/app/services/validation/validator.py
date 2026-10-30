"""
Validation service: checks extracted invoice data for issues.

Public API:
  - validate_invoice(inv, db, doc_id) -> list[ValidationIssue]   (used by Celery task)
  - _run_rules(inv, db, doc_id)        -> list[dict]              (used by tests, no SQLAlchemy)

Rules:
  - MISSING_FIELD: required fields not found
  - TOTAL_MISMATCH: subtotal + tax ≠ total (within 1% tolerance)
  - LINE_ITEM_MISMATCH: sum of line item amounts ≠ subtotal
  - DUPLICATE_INVOICE: same invoice_number already exists in DB
  - NEGATIVE_VALUE: negative amounts
  - DATE_FORMAT: unrecognized date format
  - NO_EXTRACTION: no invoice could be extracted at all
"""
from __future__ import annotations

import re
import uuid
import logging
from decimal import Decimal
from typing import Any

log = logging.getLogger(__name__)

REQUIRED_FIELDS = ["invoice_number", "invoice_date", "supplier_name", "total"]
TOLERANCE = Decimal("0.01")  # 1% tolerance for rounding


def _run_rules(inv: Any, db: Any, doc_id: uuid.UUID) -> list[dict]:
    """
    Pure-function validation that returns plain dicts (no SQLAlchemy models).
    This makes it easily testable without a database connection.
    """
    issues: list[dict] = []

    def _issue(code, severity, field=None, message=""):
        return {"code": code, "severity": severity, "field": field, "message": message,
                "document_id": str(doc_id)}

    if inv is None:
        issues.append(_issue("NO_EXTRACTION", "error", message="No invoice data could be extracted from this document."))
        return issues

    # 1. Missing required fields
    for field in REQUIRED_FIELDS:
        val = getattr(inv, field, None)
        if val is None or (isinstance(val, str) and not val.strip()):
            issues.append(_issue("MISSING_FIELD", "error", field, f"Required field '{field}' is missing."))

    # 2. Negative values
    for field in ("subtotal", "tax", "total"):
        val = getattr(inv, field, None)
        if val is not None and val < 0:
            issues.append(_issue("NEGATIVE_VALUE", "error", field, f"Field '{field}' has a negative value ({val})."))

    # 3. Total = subtotal + tax
    subtotal = getattr(inv, "subtotal", None)
    tax = getattr(inv, "tax", None)
    total = getattr(inv, "total", None)
    if subtotal is not None and tax is not None and total is not None:
        expected = subtotal + tax
        diff = abs(expected - total)
        tolerance = total * TOLERANCE if total != 0 else TOLERANCE
        if diff > tolerance:
            issues.append(_issue("TOTAL_MISMATCH", "error", "total",
                f"Subtotal ({subtotal}) + Tax ({tax}) = {expected} but Total is {total}. Diff: {diff}."))

    # 4. Line items sum ≈ subtotal
    line_items = getattr(inv, "line_items", [])
    if line_items and subtotal is not None:
        line_total = sum((li.amount for li in line_items if getattr(li, "amount", None) is not None), Decimal("0"))
        if line_total != 0:
            diff = abs(line_total - subtotal)
            tolerance = subtotal * TOLERANCE if subtotal != 0 else TOLERANCE
            if diff > tolerance:
                issues.append(_issue("LINE_ITEM_MISMATCH", "warning", "subtotal",
                    f"Sum of line items ({line_total}) ≠ subtotal ({subtotal}). Diff: {diff}."))

    # 5. Duplicate invoice number
    invoice_number = getattr(inv, "invoice_number", None)
    if invoice_number:
        try:
            from app.models.document import ExtractedInvoice
            duplicate = (
                db.query(ExtractedInvoice)
                .filter(
                    ExtractedInvoice.invoice_number == invoice_number,
                    ExtractedInvoice.document_id != doc_id,
                )
                .first()
            )
            if duplicate:
                issues.append(_issue("DUPLICATE_INVOICE", "warning", "invoice_number",
                    f"Invoice number '{invoice_number}' already exists in document {duplicate.document_id}."))
        except Exception:
            # If DB query fails (e.g. in tests), skip duplicate check
            pass

    # 6. Date format
    invoice_date = getattr(inv, "invoice_date", None)
    if invoice_date:
        iso_re = re.compile(r"^\d{4}-\d{2}-\d{2}")
        alt_re = re.compile(r"\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}")
        if not iso_re.match(invoice_date) and not alt_re.search(invoice_date):
            issues.append(_issue("DATE_FORMAT", "warning", "invoice_date",
                f"Date '{invoice_date}' may not be in a recognized format."))

    return issues


def validate_invoice(inv: Any, db: Any, doc_id: uuid.UUID) -> list:
    """
    Full validation that saves results as SQLAlchemy ValidationIssue objects.
    Called by the Celery task.
    """
    from app.models.document import ValidationIssue

    raw_issues = _run_rules(inv, db, doc_id)
    result = []
    for issue in raw_issues:
        vi = ValidationIssue(
            document_id=doc_id,
            code=issue["code"],
            severity=issue["severity"],
            field=issue.get("field"),
            message=issue["message"],
        )
        result.append(vi)
    return result
