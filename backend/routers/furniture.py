from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db

router = APIRouter()


@router.get("/{job_id}")
async def get_furniture(job_id: str, db: AsyncSession = Depends(get_db)):
    # TODO: job_id로 DB 조회 후 Job 결과 반환
    # 반환 예시: {"job_id": "...", "status": "completed", "glb_url": "...", "dimensions": {...}}
    raise NotImplementedError
