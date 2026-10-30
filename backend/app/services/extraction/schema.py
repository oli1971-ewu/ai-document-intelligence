from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field, field_validator


class LineItemModel(BaseModel):
    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None


class InvoiceModel(BaseModel):
    invoice_number: str | None = None
    invoice_date: str | None = None  # ISO 8601 preferred; raw accepted
    supplier_name: str | None = None
    customer_name: str | None = None
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total: Decimal | None = None
    currency: str | None = Field(default=None, max_length=8)
    line_items: list[LineItemModel] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator("subtotal", "tax", "total", mode="before")
    @classmethod
    def _coerce_decimal(cls, v: Any):
        if v in (None, "", "null"):
            return None
        try:
            if isinstance(v, str):
                v = v.replace(",", "").replace("$", "").replace("€", "").replace("£", "").strip()
            return Decimal(str(v))
        except (InvalidOperation, ValueError):
            return None
