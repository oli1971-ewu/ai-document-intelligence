"""
Search API.

GET /api/search?q=...&mode=keyword|semantic&limit=20
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.document import Document, ExtractedInvoice

router = APIRouter()


@router.get("")
def search(
    q: str = Query(..., min_length=1),
    mode: str = Query("keyword", pattern="^(keyword|semantic)$"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if mode == "keyword":
        return _keyword_search(q, limit, db)
    else:
        return _semantic_search(q, limit, db)


def _keyword_search(q: str, limit: int, db: Session) -> dict:
    # PostgreSQL full-text search + ILIKE fallback
    try:
        rows = db.execute(
            text("""
                SELECT d.id, d.filename, d.status, d.doc_type, d.created_at,
                       e.invoice_number, e.supplier_name, e.total, e.currency,
                       ts_rank(d.search_tsv, plainto_tsquery('english', :q)) AS rank
                FROM documents d
                LEFT JOIN extracted_invoices e ON e.document_id = d.id
                WHERE d.search_tsv @@ plainto_tsquery('english', :q)
                   OR d.filename ILIKE :like
                   OR e.invoice_number ILIKE :like
                   OR e.supplier_name ILIKE :like
                ORDER BY rank DESC, d.created_at DESC
                LIMIT :limit
            """),
            {"q": q, "like": f"%{q}%", "limit": limit},
        ).fetchall()
    except Exception:
        # Fallback: simple ILIKE
        rows = db.execute(
            text("""
                SELECT d.id, d.filename, d.status, d.doc_type, d.created_at,
                       e.invoice_number, e.supplier_name, e.total, e.currency,
                       0.0 AS rank
                FROM documents d
                LEFT JOIN extracted_invoices e ON e.document_id = d.id
                WHERE d.filename ILIKE :like
                   OR e.invoice_number ILIKE :like
                   OR e.supplier_name ILIKE :like
                ORDER BY d.created_at DESC
                LIMIT :limit
            """),
            {"like": f"%{q}%", "limit": limit},
        ).fetchall()

    results = [
        {
            "id": str(r[0]),
            "filename": r[1],
            "status": r[2],
            "doc_type": r[3],
            "created_at": r[4].isoformat() if r[4] else None,
            "invoice_number": r[5],
            "supplier_name": r[6],
            "total": float(r[7]) if r[7] is not None else None,
            "currency": r[8],
            "score": float(r[9]) if r[9] else 0.0,
        }
        for r in rows
    ]
    return {"query": q, "mode": "keyword", "count": len(results), "results": results}


def _semantic_search(q: str, limit: int, db: Session) -> dict:
    """Semantic search using pgvector cosine similarity."""
    try:
        from sentence_transformers import SentenceTransformer
        from app.core.config import settings

        model = SentenceTransformer(settings.EMBEDDING_MODEL)
        query_vec = model.encode(q).tolist()
        vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"

        rows = db.execute(
            text("""
                SELECT d.id, d.filename, d.status, d.doc_type, d.created_at,
                       e.invoice_number, e.supplier_name, e.total, e.currency,
                       1 - (d.embedding <=> :vec::vector) AS score
                FROM documents d
                LEFT JOIN extracted_invoices e ON e.document_id = d.id
                WHERE d.embedding IS NOT NULL
                ORDER BY d.embedding <=> :vec::vector
                LIMIT :limit
            """),
            {"vec": vec_str, "limit": limit},
        ).fetchall()

        results = [
            {
                "id": str(r[0]),
                "filename": r[1],
                "status": r[2],
                "doc_type": r[3],
                "created_at": r[4].isoformat() if r[4] else None,
                "invoice_number": r[5],
                "supplier_name": r[6],
                "total": float(r[7]) if r[7] is not None else None,
                "currency": r[8],
                "score": float(r[9]) if r[9] else 0.0,
            }
            for r in rows
        ]
        return {"query": q, "mode": "semantic", "count": len(results), "results": results}

    except Exception as e:
        # Fall back to keyword
        result = _keyword_search(q, limit, db)
        result["mode"] = "keyword_fallback"
        result["note"] = f"Semantic search unavailable: {e}"
        return result
