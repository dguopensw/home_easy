"""POST /furniture/gen/start  — 파이프라인 시작
GET  /furniture/gen/status/{job_id} — SSE로 진행 상태 스트리밍
"""

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services.generation_service import run_pipeline_sse

router = APIRouter()


class StartRequest(BaseModel):
    source_url: str


@router.post("/start")
async def start_generation(body: StartRequest, db: AsyncSession = Depends(get_db)):
    job_id = str(uuid.uuid4())
    return {"job_id": job_id, "source_url": body.source_url}


@router.get("/status/{job_id}")
async def get_status(job_id: str, db: AsyncSession = Depends(get_db)):
    return StreamingResponse(
        run_pipeline_sse(job_id, db),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
