"""
AI Invoice Extractor.

Supports three modes:
  - LLM_PROVIDER=gemini  → Google Gemini API
  - LLM_PROVIDER=openai  → OpenAI GPT-4o
  - LLM_PROVIDER=none    → rule-based regex fallback

Always returns an InvoiceModel or None. Never invents values.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import settings
from app.services.extraction.schema import InvoiceModel, LineItemModel

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a financial document parser. Extract invoice data from the provided text.
Return ONLY a valid JSON object with these exact keys:
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

RULES:
- Do NOT invent or guess values. If a field is not present, use null.
- For numbers, return numeric values only (no currency symbols).
- confidence reflects how certain you are (0=guessing, 1=very clear).
- Return ONLY the JSON, no explanation."""


def extract_invoice(text: str, structured: dict[str, Any] = None) -> InvoiceModel | None:
    """Main entry point. Returns parsed InvoiceModel or None."""
    if not text or not text.strip():
        return None

    provider = settings.LLM_PROVIDER.lower()

    try:
        if provider == "gemini":
            return _extract_gemini(text)
        elif provider == "openai":
            return _extract_openai(text)
        else:
            return _extract_rule_based(text)
    except Exception as e:
        log.error("LLM extraction failed, falling back to rule-based: %s", e)
        return _extract_rule_based(text)


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

def _extract_gemini(text: str) -> InvoiceModel | None:
    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        settings.LLM_MODEL,
        system_instruction=SYSTEM_PROMPT,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.0,
        ),
    )
    # Truncate to ~30k chars to stay within token limits
    snippet = text[:30_000]
    response = model.generate_content(snippet)
    raw = response.text
    return _parse_llm_response(raw)


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

def _extract_openai(text: str) -> InvoiceModel | None:
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    snippet = text[:30_000]
    resp = client.chat.completions.create(
        model=settings.LLM_MODEL if hasattr(settings, "LLM_MODEL") else "gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract invoice data from:\n\n{snippet}"},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )
    raw = resp.choices[0].message.content
    return _parse_llm_response(raw)


# ---------------------------------------------------------------------------
# Parse LLM JSON response
# ---------------------------------------------------------------------------

def _parse_llm_response(raw: str) -> InvoiceModel | None:
    if not raw:
        return None
    # Strip markdown code fences if present
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)
    try:
        data = json.loads(raw)
        return InvoiceModel(**data)
    except Exception as e:
        log.error("Failed to parse LLM JSON: %s | Raw: %.200s", e, raw)
        return None


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------

_NUM_RE = re.compile(r"[\d,]+(?:\.\d+)?")


def _find_amount(text: str, *labels: str) -> float | None:
    for label in labels:
        pat = re.compile(
            rf"\b{label}\b(?:\s*\([^)\n\r]*\))?[\s:]*[$€£]?\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE
        )
        m = pat.search(text)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                pass
    return None


def _find_str(text: str, *labels: str, maxlen: int = 200) -> str | None:
    for label in labels:
        pat = re.compile(rf"\b{label}\b[\s:#]*([^\n\r]{{1,{maxlen}}})", re.IGNORECASE)
        m = pat.search(text)
        if m:
            return m.group(1).strip()
    return None


def _extract_rule_based(text: str) -> InvoiceModel:
    invoice_number = _find_str(text, "invoice[\\s#]*no", "invoice[\\s#]*number", "inv[\\s#]*no", "inv#")
    invoice_date = _find_str(text, "invoice date", "date of invoice", "date issued", "issue date", "date")
    supplier_name = _find_str(text, "from", "vendor", "supplier", "billed by", "seller")
    customer_name = _find_str(text, "to", "bill to", "customer", "client", "buyer", "sold to")
    subtotal = _find_amount(text, "subtotal", "sub total", "sub-total", "net amount")
    tax = _find_amount(text, r"tax", r"vat", r"gst", r"hst")
    total = _find_amount(text, "total", "amount due", "total due", "grand total", "balance due")

    # Currency detection
    currency = None
    if re.search(r"\$", text):
        currency = "USD"
    elif re.search(r"€", text):
        currency = "EUR"
    elif re.search(r"£", text):
        currency = "GBP"
    elif re.search(r"CAD", text, re.I):
        currency = "CAD"

    # Confidence: rough heuristic
    found = sum(1 for v in [invoice_number, invoice_date, supplier_name, total] if v is not None)
    confidence = round(found / 4 * 0.7, 4)  # max 0.7 for rule-based

    return InvoiceModel(
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        supplier_name=supplier_name,
        customer_name=customer_name,
        subtotal=subtotal,
        tax=tax,
        total=total,
        currency=currency,
        line_items=[],
        confidence=confidence,
    )
