from typing import Any

from packages.auth_core.database import db


class SchedulingRepository:
    def get_appointments_by_date_range(
        self,
        start_date: str,
        end_date: str,
        org_id: str,
        professional_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query = db.client.table("appointments").select(
            "*, patient:patients(name, phone), professional:professionals(name), service:service_catalog(name, price)"
        )

        if org_id and org_id != 'ALL':
            query = query.eq("organization_id", org_id)

        if professional_id:
            query = query.eq("professional_id", professional_id)

        query = query.gte('scheduled_at', f"{start_date}T00:00:00.000Z")
        query = query.lte('scheduled_at', f"{end_date}T23:59:59.999Z")

        result = query.execute()
        return result.data

    def update_appointment_date(self, appointment_id: str, new_date: str, org_id: str) -> list[dict[str, Any]]:
        query = db.client.table("appointments").update({"scheduled_at": new_date})
        if org_id and org_id != 'ALL':
            query = query.eq("organization_id", org_id)
        query = query.eq("id", appointment_id)

        result = query.execute()
        return result.data
