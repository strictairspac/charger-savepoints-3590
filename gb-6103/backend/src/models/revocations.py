from sqlalchemy import BigInteger, Column, Integer, String, Table
from .base import metadata


revocations = Table(
    "revocations", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("code", String(32), unique=True, nullable=False),
    Column("meter", String(24), nullable=False, index=True),
    Column("invalid_from", BigInteger, nullable=False),
    Column("invalid_to", BigInteger, nullable=False),
    Column("note", String(500), nullable=False, default=""),
    Column("actor", String(48), nullable=False),
    Column("created_at", BigInteger, nullable=False),
)


# Single-row mutex: revocation registration and clearance signing both hold it
# with FOR UPDATE, so a revoked reading can never be released concurrently.
clearance_guard = Table(
    "clearance_guard", metadata,
    Column("id", Integer, primary_key=True),
)
