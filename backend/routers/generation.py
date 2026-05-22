import json
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests

from core import OUTPUT_DIR
from services.pipeline_service import PipelineService

router = APIRouter()
_pipeline = PipelineService()


class ProcessRequest(BaseModel):
    url: str = ""
    selected_image_index: int = 0


def _public_base_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    )
    return f"{proto}://{host}".rstrip("/")


@router.post("/process")
def api_process(body: ProcessRequest, request: Request):
    """전체 파이프라인 실행: 스크래핑 → 마스킹 → 치수 추정."""
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL을 입력해주세요.")

    result, status_code = _pipeline.run_pipeline(
        url,
        body.selected_image_index,
        backend_public_url=_public_base_url(request),
    )
    return JSONResponse(content=result, status_code=status_code)


@router.post("/gen/start")
async def start_generation(url: str):
    """(레거시 호환) 파이프라인 시작 — /api/process 사용을 권장합니다."""
    if not url:
        raise HTTPException(status_code=400, detail="URL을 입력해주세요.")
    result, status_code = _pipeline.run_pipeline(url, 0)
    job_id = result.get("job_id", "unknown")
    return JSONResponse(content={"job_id": job_id, "status": "completed"}, status_code=status_code)


@router.get("/gen/status/{job_id}")
async def get_generation_status(job_id: str):
    """(레거시 호환) 작업 상태 조회."""
    result_file = OUTPUT_DIR / job_id / "result.json"
    if not result_file.exists():
        raise HTTPException(status_code=404, detail="Job not found")

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

    return JSONResponse(content=data)
