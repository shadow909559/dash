"""Test create_user directly."""
import asyncio
import uuid
from dash_backend.db.session import AsyncSessionLocal
from dash_backend.auth.service import create_user
from dash_backend.auth.schemas import RegisterRequest


async def main():
    suffix = uuid.uuid4().hex[:8]
    payload = RegisterRequest(
        email=f"direct-{suffix}@test.com",
        username=f"direct-{suffix}",
        password="testpass123",
    )
    print(f"Attempting to create user: {payload.email} / {payload.username}")

    async with AsyncSessionLocal() as session:
        try:
            user = await create_user(session, payload)
            print(f"SUCCESS: Created user id={user.id} email={user.email}")
        except Exception as e:
            print(f"FAILED: {type(e).__name__}: {e}")
            await session.rollback()


if __name__ == "__main__":
    asyncio.run(main())