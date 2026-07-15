"""Debug create_user to find real error."""
import asyncio
import uuid
import traceback
from sqlalchemy import text
from dash_backend.db.session import AsyncSessionLocal
from dash_backend.auth.service import create_user, hash_password
from dash_backend.auth.schemas import RegisterRequest
from dash_backend.db.models.user import User


async def main():
    suffix = uuid.uuid4().hex[:8]
    email = f"debug2-{suffix}@test.com"
    username = f"debug2-{suffix}"

    async with AsyncSessionLocal() as session:
        # Check existing
        result = await session.execute(
            text("SELECT id FROM users WHERE email = :e OR username = :u"),
            {"e": email, "u": username},
        )
        existing = result.fetchone()
        print(f"Existing check: {existing}")

        print(f"Creating user manually...")
        user = User(
            email=email,
            username=username,
            password_hash=hash_password("testpass123"),
        )
        session.add(user)
        try:
            await session.commit()
            await session.refresh(user)
            print(f"SUCCESS: id={user.id}")
        except Exception as e:
            await session.rollback()
            print(f"FAILED: {type(e).__name__}: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())