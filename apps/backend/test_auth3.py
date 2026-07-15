"""Debug auth test."""
import httpx
import asyncio
import uuid

BASE = "http://localhost:8000/api/v1"


async def main():
    suffix = uuid.uuid4().hex[:8]
    email = f"debug-{suffix}@test.com"
    username = f"debug-{suffix}"

    async with httpx.AsyncClient(base_url=BASE) as c:
        # Register
        print(f"Registering with email={email} username={username}")
        r = await c.post(
            "/auth/register",
            json={"email": email, "username": username, "password": "testpass123"},
        )
        print(f"Status: {r.status_code}")
        print(f"Body: {r.json()}")

        if r.status_code == 201:
            print("SUCCESS: Registration works!")
            token = r.json()["access_token"]

            # Login
            r2 = await c.post(
                "/auth/login",
                json={"email": email, "password": "testpass123"},
            )
            print(f"\nLogin status: {r2.status_code}")
            print(f"Login body: {r2.json()}")

            # /me
            r3 = await c.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            print(f"\n/me status: {r3.status_code}")
            print(f"/me body: {r3.json()}")


if __name__ == "__main__":
    asyncio.run(main())