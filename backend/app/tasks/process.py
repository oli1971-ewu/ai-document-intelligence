"""
Background Celery task: full document processing pipeline.
  1. Parse / extract raw text
  2. Run LLM-based invoice extraction
  3. Validate extracted data
  4. Save results + embeddings to DB
"""
from __future__ import annotations

import hashlib
import logging
import time
import uuid
from decimal import Decimal

from celery import shared_task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.document import (
    Document, ExtractedInvoice, LineItem, ValidationIssue, ProcessingEvent,
)
from app.services.processing.pipeline import process_document
from app.services.extraction.extractor import extract_invoice
from app.services.validation.validator import validate_invoice

log = logging.getLogger(__name__)


def _event(db: Session, doc_id, stage: str, status: str, msg: str = None, ms: int = None):
    ev = ProcessingEvent(
        document_id=doc_id, stage=stage, status=status, message=msg, duration_ms=ms
    )
    db.add(ev)
    db.commit()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_document_task(self, document_id: str):
    doc_id = uuid.UUID(document_id)
    db: Session = SessionLocal()

    try:
        doc = db.get(Document, doc_id)
        if not doc:
            log.error("Document %s not found", document_id)
            return

        doc.status = "processing"
        db.commit()

        # ------------------------------------------------------------------
        # Stage 1: Document parsing / OCR
        # ------------------------------------------------------------------
        t0 = time.time()
        _event(db, doc_id, "processing", "started")

        result = process_document(doc.storage_path, doc.filename)

        ms = int((time.time() - t0) * 1000)
        if not result.success:
            doc.status = "failed"
            doc.error = result.error
            db.commit()
            _event(db, doc_id, "processing", "failed", result.error, ms)
            return

        doc.doc_type = result.doc_type
        doc.page_count = result.page_count
        doc.extracted_text = result.text[:500_000] if result.text else ""  # guard
        doc.status = "extracted"
        db.commit()
        _event(db, doc_id, "processing", "ok", f"doc_type={result.doc_type}", ms)

        # ------------------------------------------------------------------
        # Stage 2: AI Invoice Extraction
        # ------------------------------------------------------------------
        t0 = time.time()
        _event(db, doc_id, "extraction", "started")

        invoice_data = extract_invoice(result.text, structured=result.structured)
        ms = int((time.time() - t0) * 1000)

        if invoice_data:
            # Upsert ExtractedInvoice
            existing = db.query(ExtractedInvoice).filter_by(document_id=doc_id).first()
            if existing:
                inv = existing
            else:
                inv = ExtractedInvoice(document_id=doc_id)
                db.add(inv)

            inv.invoice_number = invoice_data.invoice_number
            inv.invoice_date = invoice_data.invoice_date
            inv.supplier_name = invoice_data.supplier_name
            inv.customer_name = invoice_data.customer_name
            inv.subtotal = invoice_data.subtotal
            inv.tax = invoice_data.tax
            inv.total = invoice_data.total
            inv.currency = invoice_data.currency
            inv.confidence = invoice_data.confidence
            inv.source = "llm" if settings.LLM_PROVIDER != "none" else "rule"
            inv.raw_json = invoice_data.model_dump(mode="json")
            db.flush()

            # Line items
            db.query(LineItem).filter_by(invoice_id=inv.id).delete()
            for pos, item in enumerate(invoice_data.line_items or []):
                li = LineItem(
                    invoice_id=inv.id,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    amount=item.amount,
                    position=pos,
                )
                db.add(li)

            db.commit()
            _event(db, doc_id, "extraction", "ok", None, ms)
        else:
            _event(db, doc_id, "extraction", "failed", "No invoice data extracted", ms)

        # ------------------------------------------------------------------
        # Stage 3: Embedding (optional, local sentence-transformers)
        # ------------------------------------------------------------------
        try:
            _embed_document(db, doc, result.text)
        except Exception as e:
            log.warning("Embedding failed (non-fatal): %s", e)

        # ------------------------------------------------------------------
        # Stage 4: Validation
        # ------------------------------------------------------------------
        t0 = time.time()
        _event(db, doc_id, "validation", "started")

        inv_obj = db.query(ExtractedInvoice).filter_by(document_id=doc_id).first()
        issues = validate_invoice(inv_obj, db, doc_id)

        # Clear old issues
        db.query(ValidationIssue).filter_by(document_id=doc_id).delete()
        for issue in issues:
            db.add(issue)
        db.commit()

        ms = int((time.time() - t0) * 1000)
        has_errors = any(i.severity == "error" for i in issues)
        doc.status = "needs_review" if has_errors else "completed"
        db.commit()
        _event(db, doc_id, "validation", "ok", f"{len(issues)} issues", ms)

    except Exception as exc:
        log.exception("Task failed for doc %s", document_id)
        db.rollback()
        try:
            doc = db.get(Document, doc_id)
            if doc:
                doc.status = "failed"
                doc.error = str(exc)
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)
    finally:
        db.close()


def _embed_document(db: Session, doc: Document, text: str):
    """Generate embedding using local sentence-transformers (no API cost)."""
    if not text or not text.strip():
        return
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(settings.EMBEDDING_MODEL)
        # Use first 5000 chars to keep it fast
        embedding = model.encode(text[:5000]).tolist()
        doc.embedding = embedding
        db.commit()
    except ImportError:
        pass  # sentence-transformers not installed, skip
