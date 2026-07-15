"""Check existing users in database."""
import asyncio
from sqlalchemy import text
from dash_backend.db.session import engine


async def main():
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT id, email, username FROM users"))
        rows = result.fetchall()
        print(f"Found {len(rows)} users:")
        for row in rows:
            print(f"  id={row[0]} email={row[1]} username={row[2]}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())