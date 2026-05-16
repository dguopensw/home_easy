"""GET /furniture/{job_id} — 완료된 job 결과 조회."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.job import Job

router = APIRouter()


@router.get("/{job_id}")
async def get_furniture(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.job_id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.job_id,
        "source_url": job.source_url,
        "dimensions": job.dimensions,
        "glb_url": job.glb_url,
        "created_at": job.created_at,
    }
