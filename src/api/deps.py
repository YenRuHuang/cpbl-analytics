"""FastAPI dependencies — DB session injection."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from src.db.engine import get_db


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI Depends-compatible generator wrapping the get_db context manager.

    Usage::

        @router.get("/example")
        def example(db: Session = Depends(get_db_session)):
            ...
    """
    with get_db() as session:
        yield session
