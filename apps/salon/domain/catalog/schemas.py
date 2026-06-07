from uuid import UUID

from pydantic import BaseModel

from packages.models.enums import Vertical


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
    requires_anamnesis: bool = False
    recall_days: int | None = None
    is_active: bool = True

class ProfessionalBase(BaseModel):
    name: str
    specialty: str | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool = True
    appointment_buffer_minutes: int = 15
