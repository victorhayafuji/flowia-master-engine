from uuid import UUID

from pydantic import BaseModel

from packages.models.enums import Vertical


class DayHours(BaseModel):
    start: str  # "HH:MM"
    end: str  # "HH:MM"


class BreakTime(BaseModel):
    start: str  # "HH:MM"
    end: str  # "HH:MM"


class OrganizationBase(BaseModel):
    name: str
    slug: str
    vertical: Vertical
    phone: str | None = None
    email: str | None = None
    timezone: str = "America/Sao_Paulo"
    is_active: bool = True

class ServiceCatalogBase(BaseModel):
    name: str
    description: str | None = None
    duration_minutes: int
    price: float | None = None
    category: str | None = None
    professional_id: UUID | None = None
    professional_ids: list[UUID] | None = None
    requires_anamnesis: bool = False
    recall_days: int | None = None
    is_active: bool = True

class ServiceCatalogUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    duration_minutes: int | None = None
    price: float | None = None
    category: str | None = None
    professional_ids: list[UUID] | None = None
    requires_anamnesis: bool | None = None
    recall_days: int | None = None
    is_active: bool | None = None

class ProfessionalBase(BaseModel):
    name: str
    specialty: str | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool = True
    appointment_buffer_minutes: int = 15
    working_hours: dict[str, DayHours] | None = None
    break_times: list[BreakTime] | None = None

class ProfessionalUpdate(BaseModel):
    name: str | None = None
    specialty: str | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool | None = None
    appointment_buffer_minutes: int | None = None
    working_hours: dict[str, DayHours] | None = None
    break_times: list[BreakTime] | None = None

class ServiceProfessionalsUpdate(BaseModel):
    professional_ids: list[UUID]
