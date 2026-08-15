"""main.py - FastAPI WebGUI Application for Nuvio/Xperience to AIOMetadata Bridge."""

from __future__ import annotations

import json
import os
from typing import Any
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.converter import (
    XperienceParser,
    build_final_aio_config,
    deduplicate_catalogs,
)
from app.nuvio_client import NuvioClient

app = FastAPI(
    title="Nuvio / Xperience to AIOMetadata Bridge",
    description="Web GUI to import layouts and catalogs from Nuvio and export to AIOMetadata.",
    version="1.0.2",
)

current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")
templates_dir = os.path.join(current_dir, "templates")
index_html_path = os.path.join(templates_dir, "index.html")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
nuvio_client = NuvioClient()


# Request Models
class ConvertRequest(BaseModel):
    nuvio_data: Any
    base_config: dict[str, Any] | None = None
    addon_name: str | None = None
    prefix_mode: str = "category"
    force_enabled: bool | None = None
    force_rating_posters: bool | None = None
    allow_duplicates: bool = False


class NuvioLoginRequest(BaseModel):
    email: str
    password: str
    addon_name: str | None = None
    prefix_mode: str = "category"


class NuvioTokenRequest(BaseModel):
    token: str
    addon_name: str | None = None
    prefix_mode: str = "category"


class NuvioManifestRequest(BaseModel):
    manifest_url: str
    addon_name: str | None = None
    prefix_mode: str = "category"


@app.get("/", response_class=FileResponse)
async def serve_index() -> FileResponse:
    """Renders the main single-page web GUI."""
    return FileResponse(index_html_path, media_type="text/html")


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "app": "Nuvio-AIOMetadata Bridge"}


@app.post("/api/convert")
async def convert_payload(request: ConvertRequest) -> dict[str, Any]:
    """Converts a raw JSON payload (widgets or manifest) into AIOMetadata configuration."""
    try:
        parser = XperienceParser(
            prefix_mode=request.prefix_mode,
            force_enabled=request.force_enabled,
            force_rating_posters=request.force_rating_posters,
        )
        catalogs = parser.parse(request.nuvio_data)

        if not request.allow_duplicates:
            catalogs = deduplicate_catalogs(catalogs)

        final_config = build_final_aio_config(
            catalogs=catalogs,
            base_config=request.base_config,
            addon_name=request.addon_name,
        )

        return {
            "success": True,
            "totalCatalogs": len(catalogs),
            "catalogs": catalogs,
            "aioConfig": final_config,
        }
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@app.post("/api/nuvio/login")
async def nuvio_login(request: NuvioLoginRequest) -> dict[str, Any]:
    """Logs in to Nuvio, pulls the full setup, and converts it to AIOMetadata."""
    try:
        raw_setup = await nuvio_client.authenticate_and_fetch_setup(
            email=request.email,
            password=request.password,
        )
        parser = XperienceParser(prefix_mode=request.prefix_mode)
        catalogs = deduplicate_catalogs(parser.parse(raw_setup))
        final_config = build_final_aio_config(catalogs=catalogs, addon_name=request.addon_name)

        return {
            "success": True,
            "message": "Successfully connected to Nuvio account and retrieved catalogs.",
            "totalCatalogs": len(catalogs),
            "catalogs": catalogs,
            "aioConfig": final_config,
        }
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"Nuvio login error: {ex}") from ex


@app.post("/api/nuvio/token")
async def nuvio_token(request: NuvioTokenRequest) -> dict[str, Any]:
    """Fetches setup from Nuvio using an existing session token."""
    try:
        raw_setup = await nuvio_client.fetch_by_token(token=request.token)
        parser = XperienceParser(prefix_mode=request.prefix_mode)
        catalogs = deduplicate_catalogs(parser.parse(raw_setup))
        final_config = build_final_aio_config(catalogs=catalogs, addon_name=request.addon_name)

        return {
            "success": True,
            "message": "Retrieved Nuvio setup via token.",
            "totalCatalogs": len(catalogs),
            "catalogs": catalogs,
            "aioConfig": final_config,
        }
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"Nuvio token error: {ex}") from ex


@app.post("/api/nuvio/manifest")
async def nuvio_manifest(request: NuvioManifestRequest) -> dict[str, Any]:
    """Fetches remote Stremio / Nuvio / Xperience manifest URL and converts catalogs."""
    try:
        manifest_data = await nuvio_client.fetch_manifest_url(request.manifest_url)
        parser = XperienceParser(prefix_mode=request.prefix_mode)
        catalogs = deduplicate_catalogs(parser.parse(manifest_data))
        final_config = build_final_aio_config(catalogs=catalogs, addon_name=request.addon_name)

        return {
            "success": True,
            "message": "Fetched manifest and converted catalogs.",
            "totalCatalogs": len(catalogs),
            "catalogs": catalogs,
            "aioConfig": final_config,
        }
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"Manifest fetch error: {ex}") from ex


@app.post("/api/upload")
async def upload_files(
    file: UploadFile = File(...),
    base_file: UploadFile | None = File(None),
    prefix_mode: str = Form("category"),
    addon_name: str | None = Form(None),
) -> dict[str, Any]:
    """Handles direct file upload from web interface."""
    try:
        content = await file.read()
        nuvio_data = json.loads(content.decode("utf-8"))

        base_config = None
        if base_file:
            base_content = await base_file.read()
            if base_content:
                base_config = json.loads(base_content.decode("utf-8"))

        parser = XperienceParser(prefix_mode=prefix_mode)
        catalogs = deduplicate_catalogs(parser.parse(nuvio_data))
        final_config = build_final_aio_config(
            catalogs=catalogs,
            base_config=base_config,
            addon_name=addon_name,
        )

        return {
            "success": True,
            "totalCatalogs": len(catalogs),
            "catalogs": catalogs,
            "aioConfig": final_config,
        }
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"File upload error: {ex}") from ex
