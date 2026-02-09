"""Delete the earlier added device"""
import asyncio
from sqlalchemy import text
import sys
sys.path.insert(0, 'd:/Trace/backend')
from app.models.database import engine

async def delete_device():
    async with engine.begin() as conn:
        result = await conn.execute(text("DELETE FROM devices WHERE serial_number = '00120646T014837'"))
        print(f'Deleted {result.rowcount} device(s)')

asyncio.run(delete_device())
