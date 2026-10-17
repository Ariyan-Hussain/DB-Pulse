"""DB-Pulse-owned SQLAlchemy models."""

from sqlalchemy import BigInteger, Boolean, Column, Index, Integer, Numeric, String
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class MetricSnapshot(Base):
    """One explicitly requested snapshot of selected MySQL health counters."""

    __tablename__ = "db_pulse_metric_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    captured_at = Column(DATETIME(fsp=6), nullable=False)
    connected_connections = Column(Integer, nullable=True)
    running_connections = Column(Integer, nullable=True)
    max_connections = Column(Integer, nullable=True)
    connection_utilization_percent = Column(Numeric(5, 2), nullable=True)
    server_uptime_seconds = Column(BigInteger, nullable=True)
    queries_since_start = Column(BigInteger, nullable=True)
    questions_since_start = Column(BigInteger, nullable=True)
    server_metrics_available = Column(Boolean, nullable=False)
    metrics_warning = Column(String(255), nullable=True)

    __table_args__ = (
        Index("idx_db_pulse_metric_snapshots_captured_at", "captured_at"),
    )
