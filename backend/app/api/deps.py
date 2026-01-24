from typing import Generator
from sqlalchemy.orm import Session
from app.db.session import SessionLocal


def get_db() -> Generator:
    """
    Dependency для отримання database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
