from __future__ import annotations


class AuthClientMixin:
    async def _login(
        self,
        client,
        email: str,
        password: str,
        *,
        new_password: str | None = None,
    ) -> dict:
        response = await client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        if new_password is None:
            return payload

        change_response = await client.post(
            "/api/auth/change-password",
            json={"current_password": password, "new_password": new_password},
        )
        self.assertEqual(change_response.status_code, 200, change_response.text)
        return change_response.json()
