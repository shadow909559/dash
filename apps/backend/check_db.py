"""Quick script to check database connectivity."""
import asyncio
from sqlalchemy import text
from dash_backend.db.session import engine


async def main():
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            )
            rows = result.fetchall()
            print("Existing tables:", [r[0] for r in rows])
            print("Database connection: OK")
    except Exception as e:
        print(f"Database connection failed: {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())