"""
Document REST API.

POST   /api/documents/upload          - Upload one or more files
GET    /api/documents                  - List all documents (paginated)
GET    /api/documents/{id}             - Get document details
GET    /api/documents/{id}/status      - Get processing status
GET    /api/documents/{id}/results     - Get extracted data + validation issues
PATCH  /api/documents/{id}/correct     - Manual corrections
POST   /api/documents/{id}/reprocess   - Retry failed document
DELETE /api/documents/{id}             - Delete document
"""
from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.document import Document, ExtractedInvoice, LineItem, ValidationIssue

router = APIRouter()

ALLOWED = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".xlsx", ".xls", ".csv"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _dispatch_processing(doc_id_str: str) -> None:
    import socket
    import threading
    from app.tasks.process import process_document_task

    redis_online = False
    try:
        s = socket.socket()
        s.settimeout(0.2)
        s.connect(("127.0.0.1", 6379))
        s.close()
        redis_online = True
    except Exception:
        redis_online = False

    if redis_online:
        try:
            process_document_task.delay(doc_id_str)
            return
        except Exception:
            pass

    # Thread-based background fallback when Redis is offline or Celery fails
    threading.Thread(target=process_document_task, args=(doc_id_str,), daemon=True).start()



def _doc_to_dict(doc: Document) -> dict:
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "content_type": doc.content_type,
        "size_bytes": doc.size_bytes,
        "status": doc.status,
        "doc_type": doc.doc_type,
        "page_count": doc.page_count,
        "error": doc.error,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


def _invoice_to_dict(inv: ExtractedInvoice) -> dict:
    if not inv:
        return None
    return {
        "id": str(inv.id),
        "invoice_number": inv.invoice_number,
        "invoice_date": inv.invoice_date,
        "supplier_name": inv.supplier_name,
        "customer_name": inv.customer_name,
        "subtotal": float(inv.subtotal) if inv.subtotal is not None else None,
        "tax": float(inv.tax) if inv.tax is not None else None,
        "total": float(inv.total) if inv.total is not None else None,
        "currency": inv.currency,
        "confidence": float(inv.confidence) if inv.confidence is not None else None,
        "source": inv.source,
        "line_items": [
            {
                "description": li.description,
                "quantity": float(li.quantity) if li.quantity is not None else None,
                "unit_price": float(li.unit_price) if li.unit_price is not None else None,
                "amount": float(li.amount) if li.amount is not None else None,
            }
            for li in sorted(inv.line_items, key=lambda x: x.position)
        ],
    }


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_documents(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    from app.tasks.process import process_document_task

    results = []
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED:
            results.append({
                "filename": file.filename,
                "error": f"Unsupported file type: {ext}",
            })
            continue

        # Read content
        content = await file.read()
        if len(content) > settings.MAX_UPLOAD_MB * 1024 * 1024:
            results.append({"filename": file.filename, "error": "File too large"})
            continue

        # Save to disk
        doc_id = uuid.uuid4()
        safe_name = f"{doc_id}{ext}"
        dest = upload_dir / safe_name
        with open(dest, "wb") as f:
            f.write(content)

        sha = _sha256(str(dest))

        doc = Document(
            id=doc_id,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=len(content),
            storage_path=str(dest),
            sha256=sha,
            status="pending",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # Dispatch processing asynchronously
        _dispatch_processing(str(doc_id))

        results.append({
            "id": str(doc_id),
            "filename": file.filename,
            "size_bytes": len(content),
            "status": "pending",
            "message": "Queued for processing",
        })

    return {"uploaded": len([r for r in results if "id" in r]), "results": results}


# ---------------------------------------------------------------------------
# List documents
# ---------------------------------------------------------------------------

@router.get("")
def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Document).order_by(Document.created_at.desc())
    if status:
        q = q.filter(Document.status == status)
    total = q.count()
    docs = q.offset(skip).limit(limit).all()
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "documents": [_doc_to_dict(d) for d in docs],
    }


# ---------------------------------------------------------------------------
# Get single document
# ---------------------------------------------------------------------------

@router.get("/{doc_id}")
def get_document(doc_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return _doc_to_dict(doc)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@router.get("/{doc_id}/status")
def get_status(doc_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    events = [
        {
            "stage": e.stage,
            "status": e.status,
            "message": e.message,
            "duration_ms": e.duration_ms,
            "created_at": e.created_at.isoformat(),
        }
        for e in sorted(doc.events, key=lambda x: x.created_at)
    ]

    return {
        "id": str(doc.id),
        "status": doc.status,
        "error": doc.error,
        "events": events,
    }


# ---------------------------------------------------------------------------
# Results (extracted data + validation)
# ---------------------------------------------------------------------------

@router.get("/{doc_id}/results")
def get_results(doc_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    inv = db.query(ExtractedInvoice).filter_by(document_id=doc_id).first()
    issues = db.query(ValidationIssue).filter_by(document_id=doc_id).all()

    return {
        "document": _doc_to_dict(doc),
        "invoice": _invoice_to_dict(inv),
        "validation_issues": [
            {
                "id": str(i.id),
                "code": i.code,
                "severity": i.severity,
                "field": i.field,
                "message": i.message,
            }
            for i in issues
        ],
    }


# ---------------------------------------------------------------------------
# Manual corrections
# ---------------------------------------------------------------------------

class CorrectionPayload(BaseModel):
    invoice_number: str | None = None
    invoice_date: str | None = None
    supplier_name: str | None = None
    customer_name: str | None = None
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None
    currency: str | None = None


@router.patch("/{doc_id}/correct")
def correct_document(
    doc_id: uuid.UUID,
    payload: CorrectionPayload,
    db: Session = Depends(get_db),
):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    inv = db.query(ExtractedInvoice).filter_by(document_id=doc_id).first()
    if not inv:
        inv = ExtractedInvoice(document_id=doc_id, source="manual")
        db.add(inv)

    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(inv, field, val)
    inv.source = "manual"
    doc.status = "completed"
    db.commit()

    return {"message": "Corrections saved", "invoice": _invoice_to_dict(inv)}


# ---------------------------------------------------------------------------
# Reprocess
# ---------------------------------------------------------------------------

@router.post("/{doc_id}/reprocess")
def reprocess_document(doc_id: uuid.UUID, db: Session = Depends(get_db)):
    from app.tasks.process import process_document_task

    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    doc.status = "pending"
    doc.error = None
    db.commit()

    _dispatch_processing(str(doc_id))
    return {"message": "Document queued for reprocessing", "id": str(doc_id)}


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete("/{doc_id}")
def delete_document(doc_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    # Remove file
    try:
        if os.path.exists(doc.storage_path):
            os.remove(doc.storage_path)
    except Exception:
        pass

    db.delete(doc)
    db.commit()
    return {"message": "Document deleted"}
