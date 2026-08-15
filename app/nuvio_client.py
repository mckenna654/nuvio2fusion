"""nuvio_client.py - Client for connecting to Nuvio / Xperience App APIs and Manifests."""

from __future__ import annotations

from typing import Any, ClassVar
import httpx


class NuvioClient:
    """Handles communication with Nuvio / Xperience API and manifest endpoints."""

    BASE_URLS: ClassVar[list[str]] = [
        "https://api.nuvioapp.com",
        "https://xperience-app.com",
        "https://nuvioapp.com",
    ]

    timeout: float

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    async def fetch_manifest_url(self, manifest_url: str) -> dict[str, Any]:
        """Fetches and parses a remote Stremio / Nuvio / Xperience manifest URL."""
        headers = {"User-Agent": "Nuvio-AIOMetadata-Bridge/1.0"}
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            resp = await client.get(manifest_url, headers=headers)
            resp.raise_for_status()
            res: dict[str, Any] = resp.json()
            return res

    async def authenticate_and_fetch_setup(
        self,
        email: str,
        password: str,
    ) -> dict[str, Any]:
        """Authenticates with Nuvio / Xperience backend and retrieves the full setup / widgets config."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NuvioBridge/1.0",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        login_payload = {"email": email, "password": password}
        last_error: Exception | None = None

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for base_url in self.BASE_URLS:
                try:
                    login_url = f"{base_url}/api/auth/login"
                    login_resp = await client.post(login_url, json=login_payload, headers=headers)
                    if login_resp.status_code == 200:
                        login_data: dict[str, Any] = login_resp.json()
                        token = login_data.get("token") or login_data.get("accessToken") or login_data.get("jwt")
                        user_id = login_data.get("userId") or login_data.get("id")

                        auth_headers = {**headers, "Authorization": f"Bearer {token}"}

                        endpoints = [
                            f"{base_url}/api/widgets",
                            f"{base_url}/api/layout",
                            f"{base_url}/api/users/{user_id}/widgets",
                            f"{base_url}/api/config",
                        ]

                        for ep in endpoints:
                            try:
                                get_resp = await client.get(ep, headers=auth_headers)
                                if get_resp.status_code == 200:
                                    data = get_resp.json()
                                    if data and isinstance(data, dict):
                                        return data
                            except httpx.HTTPError:
                                continue

                        return login_data
                except (httpx.HTTPError, ValueError) as ex:
                    last_error = ex
                    continue

        if last_error:
            raise RuntimeError(f"Unable to connect to Nuvio API: {last_error}") from last_error
        raise RuntimeError("Nuvio authentication failed. Please check credentials or use manifest / JSON export.")

    async def fetch_by_token(self, token: str, base_url: str = "https://xperience-app.com") -> dict[str, Any]:
        """Fetches user setup using an existing Bearer token or session ID."""
        headers = {
            "User-Agent": "Nuvio-AIOMetadata-Bridge/1.0",
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            endpoints = [
                f"{base_url}/api/widgets",
                f"{base_url}/api/layout",
                f"{base_url}/api/user/config",
            ]
            for ep in endpoints:
                try:
                    resp = await client.get(ep, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        if isinstance(data, dict):
                            return data
                except httpx.HTTPError:
                    continue
        raise RuntimeError("Could not retrieve setup using provided token.")
