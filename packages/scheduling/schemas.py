from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from packages.models.enums import AppointmentSource, AppointmentStatus


class AppointmentBase(BaseModel):
    patient_id: UUID
    professional_id: UUID
    service_id: UUID
    scheduled_at: datetime
    duration_minutes: int
    status: AppointmentStatus = AppointmentStatus.PENDING
    source: AppointmentSource = AppointmentSource.WHATSAPP

class AppointmentUpdate(BaseModel):
    scheduled_at: datetime

class ScheduleBlockBase(BaseModel):
    professional_id: UUID | None = None  # None = bloqueio da org inteira (ex: feriado)
    starts_at: datetime
    ends_at: datetime
    reason: str | None = None
    block_type: str = "manual"  # time_off | manual | holiday

class AnamnesisResponseBase(BaseModel):
    appointment_id: UUID
    patient_id: UUID
    answers: dict[str, Any]

class AnamnesisResponseCreate(AnamnesisResponseBase):
    pass

class FeedbackCreate(BaseModel):
    appointment_id: UUID
    score: int = Field(ge=1, le=5, description="NPS Score from 1 to 5")
    comment: str | None = None
