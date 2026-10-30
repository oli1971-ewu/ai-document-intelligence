# AI-Powered Document Intelligence System

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Next.js 14 Frontend                          │
│   ┌──────────────┐ ┌─────────────┐ ┌──────────┐ ┌──────────────┐  │
│   │  Upload Page  │ │ Documents   │ │ Results  │ │   Search     │  │
│   │  (Drag&Drop)  │ │  Dashboard  │ │  Viewer  │ │   Interface  │  │
│   └──────┬───────┘ └──────┬──────┘ └─────┬────┘ └──────┬───────┘  │
└──────────┼────────────────┼──────────────┼─────────────┼───────────┘
           │                │              │             │
           │          REST API (FastAPI)                │
           │                │              │             │
┌──────────▼────────────────▼──────────────▼─────────────▼───────────┐
│                         FastAPI Backend                              │
│  POST /upload  GET /documents  GET /results  PATCH /correct         │
│  GET /status   POST /reprocess DELETE /doc   GET /search            │
└──────┬────────────────────┬────────────────────────────────────────┘
       │                    │
  ┌────▼─────┐        ┌─────▼──────────────────────────────────────┐
  │  Redis   │        │    PostgreSQL + pgvector                    │
  │  Queue   │        │  ┌──────────┐ ┌────────────┐ ┌──────────┐ │
  │(Celery   │        │  │documents │ │ extracted_ │ │validation│ │
  │ Broker)  │        │  │          │ │ invoices   │ │ issues   │ │
  └────┬─────┘        │  └──────────┘ └────────────┘ └──────────┘ │
       │              │  ┌──────────┐ ┌────────────┐               │
┌──────▼──────────┐   │  │line_items│ │processing_ │               │
│  Celery Workers │   │  │          │ │ events     │               │
│                 │   │  └──────────┘ └────────────┘               │
│ ┌─────────────┐ │   └────────────────────────────────────────────┘
│ │1. Doc Parser│ │
│ │  pdfplumber │ │
│ │  PyMuPDF    │ │
│ │  openpyxl   │ │
│ │  pandas     │ │
│ └─────────────┘ │
│ ┌─────────────┐ │
│ │2. OCR Engine│ │
│ │  Tesseract  │ │
│ │  pytesseract│ │
│ └─────────────┘ │
│ ┌─────────────┐ │
│ │3. AI Extract│ │
│ │  Gemini/GPT │ │
│ │  Rule-based │ │
│ └─────────────┘ │
│ ┌─────────────┐ │
│ │4. Validator │ │
│ │  Math checks│ │
│ │  Duplicates │ │
│ └─────────────┘ │
└─────────────────┘
```

## Database Schema

### `documents`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| filename | VARCHAR(512) | NOT NULL |
| content_type | VARCHAR(128) | NOT NULL |
| size_bytes | INTEGER | DEFAULT 0 |
| storage_path | VARCHAR(1024) | NOT NULL |
| sha256 | VARCHAR(64) | INDEX |
| status | VARCHAR(32) | INDEX, DEFAULT 'pending' |
| error | TEXT | NULLABLE |
| doc_type | VARCHAR(32) | NULLABLE |
| page_count | INTEGER | NULLABLE |
| extracted_text | TEXT | NULLABLE |
| search_tsv | TSVECTOR | GIN INDEX |
| embedding | VECTOR(384) | NULLABLE, for semantic search |
| created_at | DATETIME | DEFAULT utcnow |
| updated_at | DATETIME | DEFAULT utcnow |

### `extracted_invoices`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| document_id | UUID | FK(documents), UNIQUE |
| invoice_number | VARCHAR(128) | INDEX, NULLABLE |
| invoice_date | VARCHAR(32) | NULLABLE |
| supplier_name | VARCHAR(512) | NULLABLE |
| customer_name | VARCHAR(512) | NULLABLE |
| subtotal | NUMERIC(14,2) | NULLABLE |
| tax | NUMERIC(14,2) | NULLABLE |
| total | NUMERIC(14,2) | NULLABLE |
| currency | VARCHAR(8) | NULLABLE |
| confidence | NUMERIC(5,4) | NULLABLE |
| source | VARCHAR(32) | DEFAULT 'llm' |
| raw_json | JSON | NULLABLE |
| created_at | DATETIME | DEFAULT utcnow |
| updated_at | DATETIME | DEFAULT utcnow |

### `line_items`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| invoice_id | UUID | FK(extracted_invoices) |
| description | TEXT | NULLABLE |
| quantity | NUMERIC(14,4) | NULLABLE |
| unit_price | NUMERIC(14,4) | NULLABLE |
| amount | NUMERIC(14,2) | NULLABLE |
| position | INTEGER | DEFAULT 0 |

### `validation_issues`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| document_id | UUID | FK(documents), INDEX |
| code | VARCHAR(64) | NOT NULL |
| severity | VARCHAR(16) | NOT NULL |
| field | VARCHAR(64) | NULLABLE |
| message | TEXT | NOT NULL |
| created_at | DATETIME | DEFAULT utcnow |

### `processing_events`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| document_id | UUID | FK(documents), INDEX |
| stage | VARCHAR(64) | NOT NULL |
| status | VARCHAR(32) | NOT NULL |
| message | TEXT | NULLABLE |
| duration_ms | INTEGER | NULLABLE |
| created_at | DATETIME | DEFAULT utcnow |

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/documents/upload | Upload files (multipart) |
| GET | /api/documents | List documents (paginated) |
| GET | /api/documents/{id} | Get document metadata |
| GET | /api/documents/{id}/status | Get processing status + events |
| GET | /api/documents/{id}/results | Get extracted invoice + validation |
| PATCH | /api/documents/{id}/correct | Apply manual corrections |
| POST | /api/documents/{id}/reprocess | Retry failed document |
| DELETE | /api/documents/{id} | Delete document |
| GET | /api/search?q=...&mode=keyword|semantic | Search documents |
| GET | /api/health | Health check |
| GET | /api/health/db | Database health check |

## Processing Pipeline

```
Upload → [Queue] → Parse (PDF/OCR/Excel/CSV) → AI Extract → Embed → Validate → Done
```

Status transitions:
`pending → processing → extracted → completed | needs_review | failed`

## Technology Decisions

| Choice | Reason |
|--------|--------|
| FastAPI (not NestJS) | Native Python AI/ML ecosystem, less boilerplate for data pipelines |
| Celery + Redis | Production-grade async task queue, retries, result tracking |
| PostgreSQL + pgvector | Single DB for relational + vector search (no extra infra) |
| pdfplumber + PyMuPDF | pdfplumber for digital text, PyMuPDF for OCR rendering |
| Tesseract | Free, fast, good accuracy for printed documents |
| Sentence Transformers | Free local embeddings, no API cost |
| LLM abstraction | Supports Gemini, OpenAI, and rule-based (no-key fallback) |
