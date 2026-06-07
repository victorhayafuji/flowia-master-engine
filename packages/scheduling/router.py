from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from packages.auth_core.dependencies import auth_required, tenant_context
from packages.auth_core.exceptions import DoubleBookingError
from packages.auth_core.tenant import set_tenant_context
from packages.scheduling.repository import SchedulingRepository
from packages.scheduling.schemas import AppointmentBase, AppointmentUpdate
from packages.scheduling.service import SchedulingService

router = APIRouter(prefix="/scheduling", tags=["Scheduling"])

def get_scheduling_service():
    return SchedulingService()

def get_scheduling_repository():
    return SchedulingRepository()

@router.get("/availability", dependencies=[Depends(auth_required)])
async def get_availability(
    professional_id: UUID,
    target_date: date,
    service_duration: int = 30,
    org_id: str = Depends(tenant_context),
    service: SchedulingService = Depends(get_scheduling_service)
):
    with set_tenant_context(org_id):
        slots = await service.get_available_slots(professional_id, target_date, service_duration)
        return {"professional_id": professional_id, "date": target_date, "available_slots": slots}

@router.post("/", dependencies=[Depends(auth_required)])
async def create_appointment(
    appointment: AppointmentBase,
    org_id: str = Depends(tenant_context),
    service: SchedulingService = Depends(get_scheduling_service)
):
    with set_tenant_context(org_id):
        result = await service.create_appointment(appointment)
        return {"status": "success", "data": result}

@router.get("/agenda", dependencies=[Depends(auth_required)])
async def get_agenda(
    start_date: date,
    end_date: date,
    org_id: str = Depends(tenant_context),
    service: SchedulingService = Depends(get_scheduling_service)
):
    with set_tenant_context(org_id):
        agenda = await service.get_agenda(start_date, end_date)
        return {"status": "success", "data": agenda}

@router.get("/calendar", dependencies=[Depends(auth_required)])
async def list_appointments(
    start_date: str,
    end_date: str,
    org_id: str = Depends(tenant_context),
    repo: SchedulingRepository = Depends(get_scheduling_repository)
):
    with set_tenant_context(org_id):
        data = repo.get_appointments_by_date_range(start_date, end_date, org_id)
        return {"status": "success", "data": data}

@router.post("/calendar/{appointment_id}", dependencies=[Depends(auth_required)])
async def update_appointment(
    appointment_id: str,
    update_data: AppointmentUpdate,
    org_id: str = Depends(tenant_context),
    service: SchedulingService = Depends(get_scheduling_service),
):
    with set_tenant_context(org_id):
        try:
            data = await service.reschedule_appointment(
                UUID(appointment_id),
                update_data.scheduled_at,
                organization_id=org_id,
            )
            return {"status": "success", "data": data}
        except DoubleBookingError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
