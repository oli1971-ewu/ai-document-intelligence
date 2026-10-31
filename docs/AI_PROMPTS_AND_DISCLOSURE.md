# AI Prompts and Development Disclosure

This document satisfies **Deliverable 9** of the Senior AI Engineer Assessment for the **AI-Powered Document Intelligence System**.

---

## 1. Production AI Extraction Prompts

### 1.1 In-System Extraction Prompt (`extractor.py`)

The extraction pipeline supports multi-modal LLM extraction via Google Gemini (`gemini-1.5-flash` / `gemini-1.5-pro`) and OpenAI (`gpt-4o` / `gpt-4o-mini`) using strict JSON schema enforcement and zero-hallucination guardrails:

```text
You are an expert financial document intelligence system.
Extract all invoice information from the text below.
Return a valid JSON object matching this exact schema:

{
  "invoice_number": string or null,
  "invoice_date": string (ISO 8601 preferred) or null,
  "supplier_name": string or null,
  "customer_name": string or null,
  "subtotal": number or null,
  "tax": number or null,
  "total": number or null,
  "currency": string (3-letter ISO code) or null,
  "line_items": [
    {
      "description": string or null,
      "quantity": number or null,
      "unit_price": number or null,
      "amount": number or null
    }
  ],
  "confidence": number between 0 and 1
}

STRICT GUARDRAILS & RULES:
1. ZERO HALLUCINATION POLICY: Do NOT invent, assume, or guess values. If any field is not explicitly present in the document text, return null.
2. NUMERIC SANITIZATION: For numeric fields (subtotal, tax, total, quantity, unit_price, amount), return numeric values only (e.g. 100.00, not "$100.00").
3. CONFIDENCE SCORING: Provide a calibrated confidence score between 0.0 and 1.0 reflecting OCR quality, document completeness, and field presence.
4. STRICT JSON: Return ONLY the JSON object. Do not wrap in conversational markdown or explanation.
```

### 1.2 Validation Engine Guardrails
Post-extraction, all fields are fed into an automated deterministic validation engine (`backend/app/services/validation/validator.py`):
- **Missing Required Fields**: Flags missing invoice number or missing total.
- **Financial Balance Reconciliation**: Verifies `subtotal + tax == total` within `0.05` tolerance.
- **Line Item Summation Check**: Cross-checks `sum(line_items.amount) == subtotal`.
- **Negative Values**: Flags refund or anomalous negative entries.
- **Duplicate Invoices**: Checks against existing records in PostgreSQL/SQLite to prevent double-billing.

---

## 2. Multi-Tier Fallback Strategy

To ensure 100% operational uptime, zero operational cost when API keys are not supplied, and robust processing during offline/air-gapped deployments:

1. **Primary**: Google Gemini API / OpenAI API.
2. **Deterministic Rules-Based Fallback**:
   - Advanced regular expressions (`INV-\d+`, `Total:\s*\$?\d+[\d,]*\.\d{2}`) for invoice headers, supplier names, totals, and dates.
3. **Structured Tabular Parser**:
   - Native parsing of CSV and Excel spreadsheets using pandas and openpyxl, automatically detecting line items, headers, quantities, unit prices, and row totals.

---

## 3. Disclosure of AI-Assisted Development

In compliance with Care Guide assessment transparency guidelines:

- **AI Tools Used**: Google Antigravity AI pair programming assistant.
- **Scope of AI Assistance**:
  - Boilerplate code generation (FastAPI route schemas, Next.js Tailwind component scaffolding).
  - Test suite generation (`tests/test_all.py` - 41 test cases covering failure modes, corruption, and edge cases).
  - Synthetic dataset generation (`samples/` and benchmark evaluation script).
- **Human Review & Engineering**:
  - All architectures, database schemas, portable SQLite/PostgreSQL fallbacks, background thread/Celery fallbacks, and Vercel/Cloudflare production deployments were engineered, tested, debugged, and verified by the candidate.
