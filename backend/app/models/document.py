from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    String, Integer, Numeric, DateTime, ForeignKey, Text, JSON, Index, types
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.core.config import settings


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class PortableUUID(types.TypeDecorator):
    impl = types.CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(types.CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class PortableTSVector(types.TypeDecorator):
    impl = types.Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import TSVECTOR
            return dialect.type_descriptor(TSVECTOR())
        return dialect.type_descriptor(types.Text())


class PortableVector(types.TypeDecorator):
    impl = types.Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            try:
                from pgvector.sqlalchemy import Vector
                return dialect.type_descriptor(Vector(settings.EMBEDDING_DIM))
            except Exception:
                pass
        return dialect.type_descriptor(types.Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name != "postgresql" and isinstance(value, list):
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                pass
        return value


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    storage_path: Mapped[str] = mapped_column(String(1024))
    sha256: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    # pending | processing | extracted | validated | needs_review | failed | completed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    doc_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # pdf_text | pdf_scanned | image | xlsx | xls | csv

    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_tsv = mapped_column(PortableTSVector, nullable=True)
    embedding = mapped_column(PortableVector, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    invoice: Mapped["ExtractedInvoice | None"] = relationship(
        back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    issues: Mapped[list["ValidationIssue"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    events: Mapped[list["ProcessingEvent"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


Index("ix_documents_search_tsv", Document.search_tsv, postgresql_using="gin")


class ExtractedInvoice(Base):
    __tablename__ = "extracted_invoices"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("documents.id", ondelete="CASCADE"), unique=True
    )

    invoice_number: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    invoice_date: Mapped[str | None] = mapped_column(String(32), nullable=True)  # ISO or raw
    supplier_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    tax: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)

    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="llm")  # llm | rule | manual
    raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document: Mapped[Document] = relationship(back_populates="invoice")
    line_items: Mapped[list["LineItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=_uuid)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("extracted_invoices.id", ondelete="CASCADE")
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    invoice: Mapped[ExtractedInvoice] = relationship(back_populates="line_items")


class ValidationIssue(Base):
    __tablename__ = "validation_issues"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(64))         # e.g. MISSING_FIELD, TOTAL_MISMATCH
    severity: Mapped[str] = mapped_column(String(16))     # info | warning | error
    field: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship(back_populates="issues")


class ProcessingEvent(Base):
    __tablename__ = "processing_events"

    id: Mapped[uuid.UUID] = mapped_column(PortableUUID, primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        PortableUUID, ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[str] = mapped_column(String(64))      # processing | extraction | validation | ...
    status: Mapped[str] = mapped_column(String(32))     # started | ok | failed
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship(back_populates="events")
