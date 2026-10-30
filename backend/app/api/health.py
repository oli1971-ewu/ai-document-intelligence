"""Health check endpoints."""
from fastapi import APIRouter
from app.db.session import SessionLocal

router = APIRouter()


@router.get("")
def health():
    return {"status": "ok"}


@router.get("/db")
def health_db():
    try:
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "error", "db": str(e)}
