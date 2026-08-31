"""Nuvio2Fusion: local, offline collection-layout conversion."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from fastapi.exceptions import RequestValidationError

from app.fusion import convert_to_fusion

ROOT = Path(__file__).parent
MAX_REQUEST_BYTES = 10 * 1024 * 1024
app = FastAPI(title='Nuvio2Fusion', version='2.0.4',
              description='Convert Nuvio collections into Fusion widget JSON.',
              docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')


class RequestBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope['headers'])
        if scope['method'] == 'POST':
            origin = headers.get(b'origin')
            if origin and urlsplit(origin.decode()).netloc != headers.get(b'host', b'').decode():
                return await JSONResponse({'detail': 'Cross-origin requests are blocked.'}, 403)(scope, receive, send)
            body = bytearray()
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    return
                body.extend(message.get('body', b''))
                if len(body) > MAX_REQUEST_BYTES:
                    return await JSONResponse({'detail': 'Request exceeds 10 MiB.'}, 413)(scope, receive, send)
                if not message.get('more_body'):
                    break
            consumed = False

            async def bounded_receive():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
                return await receive()
            await self.app(scope, bounded_receive, send)
        else:
            await self.app(scope, receive, send)


app.add_middleware(RequestBoundary)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Input values and mapping keys can both contain private install URLs.
    return JSONResponse({'detail': 'Invalid request fields. Supply export_data and an optional addon_urls object mapping addon IDs to URL strings.'}, status_code=422)


@app.middleware('http')
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    return response


class FusionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    export_data: Any
    addon_urls: dict[str, str] = Field(default_factory=dict)


@app.get('/')
async def index():
    return FileResponse(ROOT / 'templates' / 'index.html')


@app.get('/api/health')
async def health():
    return {'status': 'ok', 'app': 'Nuvio2Fusion', 'version': '2.0.4'}


@app.get('/api/presets/{name}')
async def preset(name: str):
    files = {'nuvio': 'nuvio_collections.json', 'fusion': 'fusion_example.json'}
    if name not in files:
        raise HTTPException(404, 'Unknown example.')
    return {'rawData': json.loads((ROOT / 'presets' / files[name]).read_text())}


@app.post('/api/fusion/convert')
async def fusion_convert(request: FusionRequest):
    try:
        return convert_to_fusion(**request.model_dump())
    except (ValueError, TypeError, AttributeError, KeyError, RecursionError):
        raise HTTPException(400, 'Invalid export or addon mapping. Use Nuvio collections JSON or Fusion widget v1 JSON, and full HTTP(S) manifest URLs for mappings. Check array/object fields.') from None
