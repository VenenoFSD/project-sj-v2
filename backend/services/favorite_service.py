from sqlalchemy.orm import Session

from backend.database import repositories


def list_favorites(db: Session, user_id: str):
    return repositories.list_favorites(db, user_id)


def add_favorite(db: Session, product_id: int, user_id: str):
    """收藏并提交。`get_db` 只负责关闭会话、不提交事务，所以写入必须在这里显式 commit。"""
    favorite = repositories.add_favorite(db, product_id, user_id)
    db.commit()
    return favorite


def remove_favorite(db: Session, product_id: int, user_id: str):
    removed = repositories.remove_favorite(db, product_id, user_id)
    db.commit()
    return removed
