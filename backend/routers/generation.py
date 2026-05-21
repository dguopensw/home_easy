from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.pipeline_service import PipelineService

router = APIRouter()
_pipeline = PipelineService()


class ProcessRequest(BaseModel):
    url: str = ""
    selected_image_index: int = 0


@router.post("/process")
def api_process(body: ProcessRequest):
    """전체 파이프라인 실행: 스크래핑 → 마스킹 → 치수 추정."""
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL을 입력해주세요.")

    result, status_code = _pipeline.run_pipeline(url, body.selected_image_index)
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
    from core import OUTPUT_DIR
    import json

    result_file = OUTPUT_DIR / job_id / "result.json"
    if not result_file.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    data = json.loads(result_file.read_text(encoding="utf-8"))
    return JSONResponse(content=data)
