from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database.session import get_db

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/{filter_type}")
def get_catalog(filter_type: str, db: Session = Depends(get_db)):
    rows = db.execute(text("SELECT item_id, name, captured_at FROM catalog_filters WHERE filter_type=:type ORDER BY name"), {"type": filter_type}).mappings().all()
    return {"items": [dict(row) for row in rows]}
