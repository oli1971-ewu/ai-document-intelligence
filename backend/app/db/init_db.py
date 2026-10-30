"Create extensions, tables, and indexes. Idempotent."
from sqlalchemy import text

from app.db.session import _get_engine, Base
from app import models  # noqa: F401 - ensure models imported


def init_db() -> None:
    eng = _get_engine()
    if eng.dialect.name == "postgresql":
        with eng.begin() as conn:
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            except Exception:
                pass

    Base.metadata.create_all(bind=eng)

    if eng.dialect.name == "postgresql":
        # Trigger to maintain tsvector automatically
        with eng.begin() as conn:
            try:
                conn.execute(text("""
                    CREATE OR REPLACE FUNCTION documents_tsv_update() RETURNS trigger AS $$
                    BEGIN
                      NEW.search_tsv :=
                        setweight(to_tsvector('english', coalesce(NEW.filename, '')), 'A') ||
                        setweight(to_tsvector('english', coalesce(NEW.extracted_text, '')), 'B');
                      RETURN NEW;
                    END
                    $$ LANGUAGE plpgsql;
                """))
                conn.execute(text("DROP TRIGGER IF EXISTS trg_documents_tsv ON documents"))
                conn.execute(text("""
                    CREATE TRIGGER trg_documents_tsv BEFORE INSERT OR UPDATE OF filename, extracted_text
                    ON documents FOR EACH ROW EXECUTE FUNCTION documents_tsv_update();
                """))
            except Exception:
                pass


if __name__ == "__main__":
    init_db()
    print("DB initialized.")
