from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.database import engine
router = APIRouter()
@router.get("/partitions")
def partitions():
    if engine is None:
        raise HTTPException(503, "Database is not configured; copy .env.example to .env and set the DB_* values")
    try:
        with engine.connect() as c:
            rows=c.execute(text("SELECT TABLE_SCHEMA, TABLE_NAME, PARTITION_NAME, PARTITION_METHOD, PARTITION_EXPRESSION, PARTITION_DESCRIPTION, TABLE_ROWS FROM information_schema.partitions WHERE TABLE_SCHEMA = DATABASE() AND PARTITION_NAME IS NOT NULL ORDER BY TABLE_NAME, PARTITION_ORDINAL_POSITION")).mappings().all()
        return {"partitions":[dict(r) for r in rows]}
    except Exception:
        raise HTTPException(503, "Partition metadata unavailable; check database access and privileges")
