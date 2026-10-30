"""Pytest configuration and fixtures."""
import os
import sys

# Ensure app module is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment variables BEFORE any app imports
# Use postgresql+psycopg2 driver which is available locally via psycopg2-binary
os.environ["DATABASE_URL"] = "postgresql+psycopg2://test:test@localhost/test"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/1"
os.environ["CELERY_RESULT_BACKEND"] = "redis://redis:6379/2"
os.environ["LLM_PROVIDER"] = "none"
os.environ["UPLOAD_DIR"] = "/tmp/test_uploads"
os.environ["GEMINI_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["EMBEDDING_DIM"] = "384"
os.environ["EMBEDDING_MODEL"] = "sentence-transformers/all-MiniLM-L6-v2"
