import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from packages.auth_core.database import SupabaseHandler

async def test():
    db = SupabaseHandler()
    res = db.client.table("appointments").select("id, scheduled_at, duration_minutes").execute()
    for row in res.data:
        print(row)

if __name__ == "__main__":
    asyncio.run(test())
