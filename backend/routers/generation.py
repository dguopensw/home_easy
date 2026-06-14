from __future__ import annotations

import asyncio
import json
import os
import time
from queue import Empty

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests
from sse_starlette.sse import EventSourceResponse

from core import OUTPUT_DIR, _core
from services.pipeline_service import PipelineService
from services.progress_manager import progress_manager
from services.scrape_store import scrape_store

router = APIRouter()
_pipeline = PipelineService()


class ProcessRequest(BaseModel):
    url: str = ""
    scrape_id: str = ""
    selected_image_index: int = 0


def _public_base_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    )
    return f"{proto}://{host}".rstrip("/")


def _format_dimensions(dimensions: dict | None) -> dict:
    dimensions = dimensions or {}
    return {
        "width": dimensions.get("width_cm") or dimensions.get("w"),
        "height": dimensions.get("height_cm") or dimensions.get("h"),
        "depth": dimensions.get("depth_cm") or dimensions.get("d"),
        "unit": "cm",
    }


def _refresh_model_generation_status(job_id: str) -> dict:
    result_file = OUTPUT_DIR / job_id / "result.json"
    if not result_file.exists():
        raise FileNotFoundError("Job not found")

    data = json.loads(result_file.read_text(encoding="utf-8"))
    model_generation = data.get("model_generation") or {}

    if model_generation.get("status") == "processing":
        trellis_base_url = os.getenv("TRELLIS_BASE_URL", "").rstrip("/")
        trellis_job_id = model_generation.get("trellis_job_id") or job_id

        if trellis_base_url:
            try:
                response = requests.get(
                    f"{trellis_base_url}/status/{trellis_job_id}",
                    timeout=10,
                )
                response.raise_for_status()
                trellis_status = response.json()
                status = trellis_status.get("status")

                if status == "completed":
                    model_generation.update({
                        "status": "completed",
                        "glb_url": trellis_status.get("glb_url"),
                        "error": None,
                    })
                elif status == "failed":
                    model_generation.update({
                        "status": "failed",
                        "error": trellis_status.get("error", "TRELLIS generation failed"),
                    })
                elif status:
                    model_generation["status"] = status

                data["model_generation"] = model_generation
                result_file.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception as e:
                model_generation["last_status_error"] = str(e)
                data["model_generation"] = model_generation

    return data


def _emit_error(job_id: str, message: str) -> None:
    progress_manager.emit(job_id, {
        "step": "error",
        "status": "error",
        "progress": 0,
        "message": message,
    })


def _emit_completed(job_id: str, result: dict) -> None:
    model_generation = result.get("model_generation") or {}
    glb_url = model_generation.get("glb_url")
    progress_manager.emit(job_id, {
        "step": "model_generation",
        "status": "completed",
        "progress": 95,
        "message": "3D 모델 생성 완료",
        "glb_url": glb_url,
    })
    progress_manager.emit(job_id, {
        "step": "completed",
        "status": "completed",
        "progress": 100,
        "glb_url": glb_url,
        "dimensions": _format_dimensions(result.get("dimensions")),
    })


def _run_process_job(
    job_id: str,
    body: ProcessRequest,
    backend_public_url: str,
    scraped_data: dict | None = None,
) -> None:
    def progress_callback(event: dict) -> None:
        progress_manager.emit(job_id, event)

    try:
        result, status_code = _pipeline.run_pipeline(
            _core.extract_listing_url(body.url),
            body.selected_image_index,
            backend_public_url=backend_public_url,
            job_id=job_id,
            progress_callback=progress_callback,
            scraped_data=scraped_data,
        )
        progress_manager.complete(job_id, result, status_code)

        if status_code >= 400 or result.get("error"):
            _emit_error(job_id, result.get("error", "처리 실패"))
            return

        model_generation = result.get("model_generation") or {}
        model_status = model_generation.get("status")
        if model_status == "processing":
            deadline = time.monotonic() + int(
                os.getenv("MODEL_GENERATION_POLL_TIMEOUT_SECONDS", "900")
            )
            latest = result
            while time.monotonic() < deadline:
                time.sleep(2)
                latest = _refresh_model_generation_status(job_id)
                progress_manager.complete(job_id, latest, 200)
                latest_model = latest.get("model_generation") or {}
                latest_status = latest_model.get("status")
                if latest_status == "completed" and latest_model.get("glb_url"):
                    _emit_completed(job_id, latest)
                    return
                if latest_status in {"failed", "failed_to_start", "not_configured", "skipped"}:
                    _emit_error(
                        job_id,
                        latest_model.get("error") or f"3D 모델 생성 실패: {latest_status}",
                    )
                    return

            _emit_error(job_id, "3D 모델 생성 시간이 초과되었습니다.")
            return

        if model_status == "completed" and model_generation.get("glb_url"):
            _emit_completed(job_id, result)
            return

        _emit_error(
            job_id,
            model_generation.get("error") or f"3D 모델 생성 완료 URL이 없습니다: {model_status}",
        )
    except Exception as e:
        _emit_error(job_id, str(e))


@router.post("/process")
def api_process(body: ProcessRequest, request: Request):
    """전체 파이프라인 실행: 스크래핑 → 마스킹 → 치수 추정."""
    url = _core.extract_listing_url(body.url)
    if not url:
        raise HTTPException(status_code=400, detail="URL을 입력해주세요.")

    result, status_code = _pipeline.run_pipeline(
        url,
        body.selected_image_index,
        backend_public_url=_public_base_url(request),
    )
    return JSONResponse(content=result, status_code=status_code)


@router.post("/process/start")
def start_process(
    body: ProcessRequest,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """전체 파이프라인을 백그라운드에서 시작하고 job_id를 즉시 반환합니다."""
    scrape_id = body.scrape_id.strip()
    scraped_data = scrape_store.get(scrape_id) if scrape_id else None

    if scrape_id and scraped_data is None:
        raise HTTPException(status_code=404, detail="Scrape result not found or expired")

    url = _core.extract_listing_url(body.url or (scraped_data or {}).get("url", ""))
    if not url:
        raise HTTPException(status_code=400, detail="URL을 입력해주세요.")

    body.url = url
    job_id = progress_manager.create_job()
    background_tasks.add_task(
        _run_process_job,
        job_id,
        body,
        _public_base_url(request),
        scraped_data,
    )
    return {"job_id": job_id}


@router.get("/process/status/{job_id}")
async def process_status(job_id: str, request: Request):
    """job_id의 진행 상태를 SSE로 전송합니다."""
    job = progress_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        sent = 0
        while True:
            if await request.is_disconnected():
                break

            while sent < len(job.events):
                event = job.events[sent]
                sent += 1
                yield {
                    "data": json.dumps(event, ensure_ascii=False),
                }
                if event.get("step") in {"completed", "error"}:
                    return

            if job.terminal:
                return

            try:
                await asyncio.to_thread(job.queue.get, True, 15)
            except Empty:
                yield {"comment": "keepalive"}

    return EventSourceResponse(event_generator())


@router.post("/gen/start")
async def start_generation(url: str):
    """(레거시 호환) 파이프라인 시작 — /api/process 사용을 권장합니다."""
    url = _core.extract_listing_url(url)
    if not url:
        raise HTTPException(status_code=400, detail="URL을 입력해주세요.")
    result, status_code = _pipeline.run_pipeline(url, 0)
    job_id = result.get("job_id", "unknown")
    return JSONResponse(content={"job_id": job_id, "status": "completed"}, status_code=status_code)


@router.get("/gen/status/{job_id}")
async def get_generation_status(job_id: str):
    """(레거시 호환) 작업 상태 조회."""
    try:
        data = _refresh_model_generation_status(job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(content=data)
