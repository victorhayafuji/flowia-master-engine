"""
Seed operacional do salão demo: org, profissionais, serviços, clientes e agendamentos.

Uso:
  python scripts/seed_salon.py
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from apps.salon.seeds.vertical_orgs import SALON_ORG_ID, VERTICAL_ORGS


def main() -> int:
    from packages.auth_core.database import db

    if not db.wait_for_ready(timeout=5):
        print("Erro: Supabase indisponível")
        return 1

    meta = VERTICAL_ORGS["salon"]
    org_id = SALON_ORG_ID

    existing = db.client.table("organizations").select("id").eq("id", org_id).execute()
    if not existing.data:
        db.client.table("organizations").insert({
            "id": org_id,
            "name": meta["name"],
            "slug": meta["slug"],
            "vertical": meta["vertical"],
            "is_active": True,
        }).execute()
        print(f"Organização criada: {meta['name']}")
    else:
        print(f"Organização já existe: {meta['name']}")

    professionals = [
        {"name": "Maria Silva", "specialty": "Cabeleireira"},
        {"name": "Ana Costa", "specialty": "Colorista"},
    ]
    prof_by_name: dict[str, str] = {}
    for prof in professionals:
        row = (
            db.client.table("professionals")
            .select("id")
            .eq("organization_id", org_id)
            .eq("name", prof["name"])
            .execute()
        )
        if row.data:
            prof_by_name[prof["name"]] = row.data[0]["id"]
            continue
        new_id = str(uuid4())
        db.client.table("professionals").insert({
            "id": new_id,
            "organization_id": org_id,
            "name": prof["name"],
            "specialty": prof["specialty"],
            "is_active": True,
        }).execute()
        prof_by_name[prof["name"]] = new_id
        print(f"  Profissional: {prof['name']}")

    maria_id = prof_by_name["Maria Silva"]
    ana_id = prof_by_name["Ana Costa"]

    services = [
        {"name": "Corte Feminino", "duration_minutes": 60, "price": 120.0, "category": "Cortes", "professional_id": maria_id},
        {"name": "Corte Masculino", "duration_minutes": 45, "price": 80.0, "category": "Cortes", "professional_id": maria_id},
        {"name": "Coloração Completa", "duration_minutes": 120, "price": 250.0, "category": "Coloração", "professional_id": ana_id},
        {"name": "Manicure", "duration_minutes": 40, "price": 45.0, "category": "Unhas", "professional_id": maria_id},
        {"name": "Combo Corte + Hidratação", "duration_minutes": 90, "price": 180.0, "category": "Combos", "professional_id": maria_id},
    ]
    service_by_name: dict[str, str] = {}
    for svc in services:
        row = (
            db.client.table("service_catalog")
            .select("id")
            .eq("organization_id", org_id)
            .eq("name", svc["name"])
            .execute()
        )
        if row.data:
            service_by_name[svc["name"]] = row.data[0]["id"]
            db.client.table("service_catalog").update({
                "professional_id": svc["professional_id"],
            }).eq("id", row.data[0]["id"]).execute()
            continue
        svc_id = str(uuid4())
        db.client.table("service_catalog").insert({
            "id": svc_id,
            "organization_id": org_id,
            **svc,
            "is_active": True,
        }).execute()
        service_by_name[svc["name"]] = svc_id
        print(f"  Serviço: {svc['name']} — R$ {svc['price']:.0f}")

    clients = [
        {"name": "Juliana Pereira", "phone": "11988887777"},
        {"name": "Carlos Mendes", "phone": "11977776666"},
    ]
    client_by_phone: dict[str, str] = {}
    for client in clients:
        row = (
            db.client.table("patients")
            .select("id")
            .eq("organization_id", org_id)
            .eq("phone", client["phone"])
            .execute()
        )
        if row.data:
            client_by_phone[client["phone"]] = row.data[0]["id"]
            continue
        cid = str(uuid4())
        db.client.table("patients").insert({
            "id": cid,
            "organization_id": org_id,
            "name": client["name"],
            "phone": client["phone"],
        }).execute()
        client_by_phone[client["phone"]] = cid
        print(f"  Cliente: {client['name']}")

    tz = timezone(timedelta(hours=-3))
    tomorrow = datetime.now(tz).replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
    day_after = tomorrow.replace(hour=14, minute=0) + timedelta(days=1)

    demo_appointments = [
        {
            "patient_id": client_by_phone["11988887777"],
            "professional_id": maria_id,
            "service_id": service_by_name["Corte Feminino"],
            "scheduled_at": tomorrow.isoformat(),
            "duration_minutes": 60,
            "status": "confirmed",
            "source": "dashboard",
        },
        {
            "patient_id": client_by_phone["11977776666"],
            "professional_id": ana_id,
            "service_id": service_by_name["Coloração Completa"],
            "scheduled_at": day_after.isoformat(),
            "duration_minutes": 120,
            "status": "confirmed",
            "source": "dashboard",
        },
    ]
    for appt in demo_appointments:
        exists = (
            db.client.table("appointments")
            .select("id")
            .eq("organization_id", org_id)
            .eq("patient_id", appt["patient_id"])
            .eq("scheduled_at", appt["scheduled_at"])
            .execute()
        )
        if exists.data:
            continue
        db.client.table("appointments").insert({
            "id": str(uuid4()),
            "organization_id": org_id,
            **appt,
        }).execute()
        print(f"  Agendamento demo: {appt['scheduled_at']}")

    print(f"\nSalão seed concluído (org {org_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
