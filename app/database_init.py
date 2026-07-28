# app/database_init.py
"""Create/drop all tables. Imports models so they register on Base.metadata."""

from app.database import engine, Base
import app.models.user       # noqa: F401  (ensures User is registered)
import app.models.calculation  # noqa: F401  (ensures Calculation is registered)


def init_db():
    Base.metadata.create_all(bind=engine)


def drop_db():
    Base.metadata.drop_all(bind=engine)


if __name__ == "__main__":
    init_db()  # pragma: no cover
