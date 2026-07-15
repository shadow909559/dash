"""Test authentication endpoints."""
import httpx
import asyncio

BASE = "http://localhost:8000/api/v1"


async def main():
    async with httpx.AsyncClient(base_url=BASE) as c:
        # Test register
        print("=== Test Register ===")
        r = await c.post(
            "/auth/register",
            json={"email": "test@test.com", "username": "testuser", "password": "testpass123"},
        )
        print(f"Status: {r.status_code}")
        print(f"Body: {r.json()}")
        print()

        if r.status_code == 201:
            # Test login
            print("=== Test Login ===")
            r2 = await c.post(
                "/auth/login",
                json={"email": "test@test.com", "password": "testpass123"},
            )
            print(f"Status: {r2.status_code}")
            data = r2.json()
            print(f"Body: {data}")
            print()

            # Test /me with token
            print("=== Test /me ===")
            token = data.get("access_token")
            if token:
                r3 = await c.get(
                    "/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
                print(f"Status: {r3.status_code}")
                print(f"Body: {r3.json()}")

            # Test duplicate register
            print()
            print("=== Test Duplicate Register ===")
            r4 = await c.post(
                "/auth/register",
                json={"email": "test@test.com", "username": "testuser", "password": "testpass123"},
            )
            print(f"Status: {r4.status_code}")
            print(f"Body: {r4.json()}")


if __name__ == "__main__":
    asyncio.run(main())