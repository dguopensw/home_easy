"""FastAPI entrypoint for the furniture dimension pipeline.

The heavy pipeline implementation currently lives in app.py as framework-neutral
functions. This module exposes the same HTTP contract through FastAPI/uvicorn so
the frontend can run without changing API paths.

Run:
    uvicorn fastapi_app:app --host 127.0.0.1 --port 5003
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import app as legacy_pipeline


PIPELINE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PIPELINE_DIR / "static"
OUTPUT_DIR = PIPELINE_DIR / "output"

legacy_pipeline.load_runtime_environment()


class ScrapeRequest(BaseModel):
    url: str = ""


class ProcessRequest(BaseModel):
    url: str = ""
    selected_image_index: Optional[int] = None
    selected_cutout_method: Optional[str] = None
    roi_bbox: Optional[List[float]] = Field(default=None, description="[x, y, w, h]")


app = FastAPI(title="Furniture Dimension Pipeline", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "framework": "fastapi"}


@app.post("/api/scrape")
def api_scrape(body: ScrapeRequest) -> JSONResponse:
    data, status_code = legacy_pipeline.scrape_listing(body.model_dump())
    return JSONResponse(content=data, status_code=status_code)


@app.post("/api/process")
def api_process(body: ProcessRequest) -> JSONResponse:
    data, status_code = legacy_pipeline.run_pipeline(body.model_dump(exclude_none=True))
    return JSONResponse(content=data, status_code=status_code)


@app.get("/api/output/{job_id}/{filename}")
def serve_output(job_id: str, filename: str) -> FileResponse:
    safe_job_id = Path(job_id).name
    safe_filename = Path(filename).name
    file_path = OUTPUT_DIR / safe_job_id / safe_filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Output file not found")
    return FileResponse(file_path)
