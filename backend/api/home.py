from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database.session import get_db

router = APIRouter(prefix="/home", tags=["home"])


@router.get("/latest")
def get_latest_home(db: Session = Depends(get_db)):
    row = db.execute(text("SELECT * FROM home_snapshots ORDER BY captured_at DESC, id DESC LIMIT 1")).mappings().first()
    return dict(row) if row else {"message": "No home snapshot"}
