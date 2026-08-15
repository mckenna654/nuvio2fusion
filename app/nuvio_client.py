"""nuvio_client.py - Client for connecting to Nuvio / Xperience App APIs and Manifests."""

from __future__ import annotations

from typing import Any, ClassVar
import httpx


class NuvioClient:
    """Handles communication with Nuvio / Xperience API and manifest endpoints."""

    BASE_URLS: ClassVar[list[str]] = [
        "https://xperience-app.com",
    ]

    timeout: float

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    def normalize_manifest_url(self, raw_url: str) -> str:
        """Cleans and standardizes a Stremio / Xperience manifest URL."""
        url = raw_url.strip()
        if url.startswith("stremio://"):
            url = "https://" + url[len("stremio://"):]
        elif not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url

        # If URL doesn't end in .json and looks like a manifest path
        if "/manifest/" in url and not url.endswith("/manifest.json") and not url.endswith(".json"):
            url = url.rstrip("/") + "/manifest.json"

        return url

    async def fetch_manifest_url(self, raw_manifest_url: str) -> dict[str, Any]:
        """Fetches and parses a remote Stremio / Nuvio / Xperience manifest URL."""
        manifest_url = self.normalize_manifest_url(raw_manifest_url)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NuvioBridge/1.0",
            "Accept": "application/json, text/plain, */*",
        }
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, verify=False) as client:
            resp = await client.get(manifest_url, headers=headers)
            resp.raise_for_status()
            res: dict[str, Any] = resp.json()
            return res

    async def authenticate_and_fetch_setup(
        self,
        email: str,
        password: str,
    ) -> dict[str, Any]:
        """Attempts authentication or guides user to use the manifest URL."""
        # If user accidentally entered their manifest URL in the email field
        if "manifest" in email.lower() or email.startswith(("http", "stremio")):
            return await self.fetch_manifest_url(email)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NuvioBridge/1.0",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        login_payload = {"email": email, "password": password}

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, verify=False) as client:
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
                except (httpx.HTTPError, ValueError):
                    continue

        raise RuntimeError(
            "Xperience / Nuvio uses token-based manifest authentication. "
            "Please copy your Stremio / Xperience Manifest URL (from the Xperience Install/Share button) "
            "or export your fusion-widgets.json file, and paste it into the 'Manifest URL' or 'Upload JSON' tab."
        )

    async def fetch_by_token(self, token: str, base_url: str = "https://xperience-app.com") -> dict[str, Any]:
        """Fetches user setup using an existing Bearer token or session ID."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NuvioBridge/1.0",
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, verify=False) as client:
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
