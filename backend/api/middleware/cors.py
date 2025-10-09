"""CORS configuration with environment-based origins and preflight handling."""
from __future__ import annotations
import os
from typing import List
from fastapi import FastAPI, Request, Response
from starlette.middleware.cors import CORSMiddleware


DEFAULT_ORIGINS = [
	"http://localhost:3000",
	"http://127.0.0.1:3000",
]


ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
ALLOWED_HEADERS = ["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"]




def get_origins() -> List[str]:
	env = os.getenv("ENV", "dev").lower()
	if env == "prod":
		csv = os.getenv("CORS_ORIGINS", "")
		return [o.strip() for o in csv.split(",") if o.strip()]
	return DEFAULT_ORIGINS




def add_cors(app: FastAPI) -> None:
	app.add_middleware(
		CORSMiddleware,
		allow_origins=get_origins(),
		allow_credentials=True,
		allow_methods=ALLOWED_METHODS,
		allow_headers=ALLOWED_HEADERS,
		expose_headers=["X-Request-ID", "X-New-Access-Token", "Retry-After"],
		max_age=86400,
	)


@app.options("/{full_path:path}")
async def preflight_handler(request: Request):
	# Starlette CORS handles most of this; explicit 200 ensures proxies behave
	return Response(status_code=200)