from fastapi import APIRouter
from app.db import check_db_connection

router = APIRouter()


@router.get("/health")
def health():
    db_ok = False

    try:
        db_ok = check_db_connection()
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
    }