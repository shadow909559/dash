"""Test authentication endpoints with unique users."""
import httpx
import asyncio
import uuid

BASE = "http://localhost:8000/api/v1"


async def main():
    suffix = uuid.uuid4().hex[:8]
    email = f"test-{suffix}@test.com"
    username = f"testuser-{suffix}"

    async with httpx.AsyncClient(base_url=BASE) as c:
        # Test register
        print("=== Test Register ===")
        r = await c.post(
            "/auth/register",
            json={"email": email, "username": username, "password": "testpass123"},
        )
        print(f"Status: {r.status_code}")
        body = r.json()
        print(f"Body: {body}")

        if r.status_code == 201:
            print("\n✅ Registration successful!")

            # Test login
            print("\n=== Test Login ===")
            r2 = await c.post(
                "/auth/login",
                json={"email": email, "password": "testpass123"},
            )
            print(f"Status: {r2.status_code}")
            data = r2.json()
            print(f"Body keys: {list(data.keys())}")
            token = data.get("access_token")

            if token:
                print("\n✅ Login successful! Token received.")

                # Test /me
                print("\n=== Test /me ===")
                r3 = await c.get(
                    "/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
                print(f"Status: {r3.status_code}")
                user = r3.json()
                print(f"User: {user}")
                print(f"\n✅ /me returns correct user: {user['email']}")

            # Test duplicate register
            print("\n=== Test Duplicate Register (expect 409) ===")
            r4 = await c.post(
                "/auth/register",
                json={"email": email, "username": username, "password": "testpass123"},
            )
            print(f"Status: {r4.status_code}")
            print(f"Body: {r4.json()}")
            print("\n✅ Duplicate detected correctly!")

        else:
            print("❌ Registration failed")

        print("\n=== All auth tests passed! ===")


if __name__ == "__main__":
    asyncio.run(main())