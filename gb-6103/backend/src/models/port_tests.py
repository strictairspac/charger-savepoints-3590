from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, Index, Integer, String, Table
from .base import metadata


# Every submitted port reading is kept, including ones whose station was held
# and rolled back, so a late calibration revocation can still trace the record.
port_tests = Table(
    "port_tests", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", ForeignKey("runs.id"), nullable=False, index=True),
    Column("position", Integer, nullable=False),
    Column("station", String(24), nullable=False),
    Column("district", String(40), nullable=False),
    Column("port_serial", String(24), nullable=False),
    Column("insulation", Integer, nullable=False),
    Column("interlock", Boolean, nullable=False),
    Column("minimum", Integer, nullable=False),
    Column("meter", String(24), nullable=False),
    Column("tested_at", BigInteger, nullable=False),
    Column("port_ok", Boolean, nullable=False),
    Column("station_decision", String(8), nullable=False),
    Column("reason", String(400), nullable=False, default=""),
    Column("recorded_at", BigInteger, nullable=False),
    Index("port_tests_meter_tested", "meter", "tested_at"),
    Index("port_tests_station_port", "station", "port_serial"),
)
