# AI-Powered Document Intelligence System

> **Senior AI Engineer Assessment Project**  
> Automated document processing, AI extraction, validation, and search

---

## 🎯 Overview

A full-stack system that ingests business documents (PDFs, images, spreadsheets, CSVs), extracts structured invoice data using AI/OCR, validates the results, and provides a searchable web interface.

---

## 🏗️ Architecture

```
Next.js Frontend ←→ FastAPI Backend ←→ PostgreSQL + pgvector
                              ↓
                    Redis Queue (Celery)
                              ↓
                    Workers: Parse → OCR → AI Extract → Validate
```

**Stack:**
| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router, TypeScript, Tailwind) |
| Backend API | FastAPI (Python 3.11) |
| Task Queue | Celery + Redis |
| Database | PostgreSQL with pgvector extension |
| OCR | Tesseract + pytesseract |
| AI Extraction | Google Gemini / OpenAI GPT-4o / Rule-based fallback |
| Embeddings | sentence-transformers (local, free) |
| Containers | Docker Compose |

---

## 🚀 Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- (Optional) Gemini or OpenAI API key for AI extraction

### 1. Clone and configure

```bash
git clone <repo-url>
cd doc-intel
```

Edit `backend/.env`:
```env
# Add your LLM API key (optional — works without one using rule-based extraction)
LLM_PROVIDER=gemini        # gemini | openai | none
GEMINI_API_KEY=your-key-here
# OR
LLM_PROVIDER=openai
OPENAI_API_KEY=your-key-here
```

### 2. Start with Docker Compose

```bash
docker compose up --build
```

This starts:
- **PostgreSQL** on port 5432 (with pgvector)
- **Redis** on port 6379
- **Backend API** on http://localhost:8000
- **Celery Worker** (background processing)
- **Frontend** on http://localhost:3000

### 3. Access the application

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API Docs | http://localhost:8000/docs |
| API Health | http://localhost:8000/api/health |

---

## 💻 Local Development (without Docker)

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Install Tesseract OCR (Windows)
# Download: https://github.com/UB-Mannheim/tesseract/wiki
# Then set: TESSDATA_PREFIX in .env

# Start PostgreSQL and Redis (via Docker)
docker run -d -p 5432:5432 -e POSTGRES_USER=docintel -e POSTGRES_PASSWORD=docintel -e POSTGRES_DB=docintel ankane/pgvector
docker run -d -p 6379:6379 redis:7-alpine

# Initialize database
python -m app.db.init_db

# Start API server
uvicorn app.main:app --reload --port 8000

# Start Celery worker (separate terminal)
celery -A app.celery_app worker --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
npm run dev       # http://localhost:3000
```

---

## 📋 Supported File Formats

| Format | Method | Notes |
|--------|--------|-------|
| PDF (digital) | pdfplumber | Fast, high accuracy |
| PDF (scanned) | PyMuPDF + Tesseract OCR | Automatic fallback |
| JPG, PNG, TIFF | Tesseract OCR | Image enhancement applied |
| XLSX, XLS | openpyxl / xlrd | Multi-sheet support |
| CSV | pandas | Auto-delimiter detection |

---

## 🤖 AI Extraction

The system extracts these fields from documents:

| Field | Description |
|-------|-------------|
| `invoice_number` | Unique invoice identifier |
| `invoice_date` | Issue date (ISO 8601 preferred) |
| `supplier_name` | Vendor/seller name |
| `customer_name` | Buyer/client name |
| `subtotal` | Pre-tax amount |
| `tax` | Tax amount |
| `total` | Total amount due |
| `currency` | 3-letter ISO code (USD, EUR, GBP...) |
| `line_items` | Array of {description, qty, unit_price, amount} |
| `confidence` | AI confidence score (0.0–1.0) |

**Never invents values** — missing fields are returned as `null`.

---

## ✅ Validation Rules

| Code | Severity | Description |
|------|----------|-------------|
| `MISSING_FIELD` | error | Required field absent |
| `TOTAL_MISMATCH` | error | subtotal + tax ≠ total |
| `NEGATIVE_VALUE` | error | Negative amount detected |
| `LINE_ITEM_MISMATCH` | warning | Line item sum ≠ subtotal |
| `DUPLICATE_INVOICE` | warning | Invoice number already exists |
| `DATE_FORMAT` | warning | Unrecognized date format |
| `NO_EXTRACTION` | error | No data could be extracted |

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/documents/upload` | Upload files (multipart/form-data) |
| `GET` | `/api/documents` | List documents (paginated) |
| `GET` | `/api/documents/{id}` | Get document metadata |
| `GET` | `/api/documents/{id}/status` | Processing status + events |
| `GET` | `/api/documents/{id}/results` | Extracted data + validation |
| `PATCH` | `/api/documents/{id}/correct` | Apply manual corrections |
| `POST` | `/api/documents/{id}/reprocess` | Retry failed document |
| `DELETE` | `/api/documents/{id}` | Delete document |
| `GET` | `/api/search?q=...&mode=keyword|semantic` | Search documents |

Full interactive docs: http://localhost:8000/docs

---

## 🧪 Running Tests

```bash
cd backend

# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=app --cov-report=html
```

---

## 📊 Sample Test Documents

Located in `samples/` directory. Generate with:

```bash
cd doc-intel
pip install reportlab openpyxl
python samples/generate_samples.py
```

| File | Description | Expected Issues |
|------|-------------|----------------|
| `sample_invoice_1.pdf` | Valid invoice, all fields | None |
| `sample_invoice_2_math_error.pdf` | Invoice with wrong total | TOTAL_MISMATCH |
| `sample_invoices.csv` | 5 invoices in CSV | None |
| `sample_invoices.xlsx` | Multi-sheet Excel | None |

---

## 📁 Project Structure

```
doc-intel/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app entry point
│   │   ├── celery_app.py           # Celery configuration
│   │   ├── api/
│   │   │   ├── documents.py        # Document CRUD endpoints
│   │   │   ├── search.py           # Search endpoints
│   │   │   └── health.py           # Health check
│   │   ├── core/
│   │   │   └── config.py           # Settings (env vars)
│   │   ├── db/
│   │   │   ├── session.py          # SQLAlchemy engine
│   │   │   └── init_db.py          # Schema init + triggers
│   │   ├── models/
│   │   │   └── document.py         # SQLAlchemy ORM models
│   │   ├── services/
│   │   │   ├── processing/
│   │   │   │   ├── pipeline.py     # Document routing
│   │   │   │   ├── pdf_extractor.py# PDF + OCR fallback
│   │   │   │   ├── ocr.py          # Tesseract wrapper
│   │   │   │   ├── image_extractor.py
│   │   │   │   └── spreadsheet_extractor.py
│   │   │   ├── extraction/
│   │   │   │   ├── extractor.py    # AI extraction (Gemini/OpenAI/rules)
│   │   │   │   └── schema.py       # InvoiceModel Pydantic schema
│   │   │   └── validation/
│   │   │       └── validator.py    # Validation engine
│   │   └── tasks/
│   │       └── process.py          # Celery task (full pipeline)
│   ├── tests/
│   │   ├── conftest.py
│   │   └── test_all.py             # 26 automated tests
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env
├── frontend/
│   ├── app/
│   │   ├── layout.tsx              # Root layout with sidebar
│   │   ├── page.tsx                # Upload page
│   │   ├── documents/
│   │   │   ├── page.tsx            # Documents dashboard
│   │   │   └── [id]/page.tsx       # Document detail + edit
│   │   └── search/
│   │       └── page.tsx            # Search interface
│   ├── components/
│   │   └── Sidebar.tsx             # Navigation sidebar
│   ├── lib/
│   │   └── api.ts                  # API client library
│   └── Dockerfile
├── docs/
│   ├── ARCHITECTURE.md             # Architecture + DB schema
│   └── EVALUATION_REPORT.md        # Metrics + test results
├── samples/
│   ├── generate_samples.py         # Sample document generator
│   └── README.md
└── docker-compose.yml
```

---

## 🔒 Security

- File type validation (extension + size limits)
- SHA-256 content hashing for deduplication
- CORS configured for frontend origin only
- No credentials in source code (env vars)
- Celery tasks isolated from API processes

---

## 📈 Performance

- **Celery workers**: Scale horizontally by increasing `--concurrency`
- **Database**: Connection pooling, GIN index for full-text search, ivfflat index for vector search
- **Large PDFs**: Streamed page-by-page; OCR only on weak pages
- **Background processing**: API returns immediately; client polls for status

---

## 🤝 AI Disclosure

This project was built with assistance from **Google Antigravity AI** for:
- Code scaffolding and boilerplate generation
- Test case generation
- Documentation writing

All AI-generated code was reviewed, tested, and modified by the developer. The AI extraction feature (Gemini API / OpenAI) is an explicit requirement of the assessment.
