"""Validated request bodies for DB-Pulse endpoints."""

from pydantic import BaseModel, ConfigDict, Field


class AnalyzeRequest(BaseModel):
    """SQL text or a bounded slow-query log excerpt; never executed by the API."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(min_length=1, max_length=10_000, description="SQL statement or slow-query log excerpt")
