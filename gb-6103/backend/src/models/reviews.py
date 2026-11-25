from sqlalchemy import JSON, BigInteger, Column, ForeignKey, String, Table
from .base import metadata


# The signed clearance keeps the exact judgment taken at signing time.
# Later revocations are shown against a live view, never written into this row.
reviews = Table(
    "reviews", metadata,
    Column("run_id", ForeignKey("runs.id"), primary_key=True),
    Column("actor", String(48), nullable=False),
    Column("note", String(500), nullable=False),
    Column("created_at", BigInteger, nullable=False),
    Column("snapshot", JSON(none_as_null=True), nullable=True),
    Column("digest", String(64), nullable=True),
)
