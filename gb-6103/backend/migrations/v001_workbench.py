from sqlalchemy import insert, select, text
from sqlalchemy.exc import IntegrityError

from src.models import audit, cases, port_tests, reviews, revocations, runs, users  # Register the tables.
from src.models.base import metadata
from src.models.revocations import clearance_guard


def _add_review_columns(connection):
    """Databases created before the clearance feature lack these columns."""
    if connection.dialect.name == "postgresql":
        connection.execute(text("ALTER TABLE reviews ADD COLUMN IF NOT EXISTS snapshot JSON"))
        connection.execute(text("ALTER TABLE reviews ADD COLUMN IF NOT EXISTS digest VARCHAR(64)"))
        return
    existing = {row[0] for row in connection.execute(text("SHOW COLUMNS FROM reviews"))}
    if "snapshot" not in existing:
        connection.execute(text("ALTER TABLE reviews ADD COLUMN snapshot JSON"))
    if "digest" not in existing:
        connection.execute(text("ALTER TABLE reviews ADD COLUMN digest VARCHAR(64)"))


def upgrade(connection):
    """Create the schema, upgrade pre-existing tables and seed the mutex row."""
    metadata.create_all(connection)
    _add_review_columns(connection)
    if connection.scalar(select(clearance_guard.c.id).where(clearance_guard.c.id == 1)) is None:
        try:
            with connection.begin_nested():
                connection.execute(insert(clearance_guard).values(id=1))
        except IntegrityError:
            pass  # Another process seeded the mutex row first.
