"""Pydantic schemas for audit logs."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: str
    entity_id: str
    actor: str
    action: str
    what_happened: str
    what_caused_it: Optional[str] = None
    action_taken: Optional[str] = None
    result: Optional[str] = None
    metadata_json: Optional[str] = None
    timestamp: datetime


class AuditLogFilter(BaseModel):
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    actor: Optional[str] = None
    action: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
