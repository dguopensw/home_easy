from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from core import OUTPUT_DIR
from database import get_db

router = APIRouter()


@router.get("/output/{job_id}/{filename}")
def serve_output(job_id: str, filename: str):
    """파이프라인 출력 파일(이미지 등)을 제공합니다."""
    safe_job_id = Path(job_id).name
    safe_filename = Path(filename).name
    file_path = OUTPUT_DIR / safe_job_id / safe_filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(file_path))


@router.get("/{job_id}")
async def get_furniture(job_id: str, db: AsyncSession = Depends(get_db)):
    """job_id로 DB 조회 후 Job 결과 반환."""
    import json

    result_file = OUTPUT_DIR / job_id / "result.json"
    if not result_file.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    data = json.loads(result_file.read_text(encoding="utf-8"))
    return data
