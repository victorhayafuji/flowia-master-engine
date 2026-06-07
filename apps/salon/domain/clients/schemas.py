from datetime import date

from pydantic import BaseModel


class PatientBase(BaseModel):
    name: str
    phone: str
    email: str | None = None
    cpf: str | None = None
    birth_date: date | None = None
    is_active: bool = True
