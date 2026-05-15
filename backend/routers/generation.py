from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db

router = APIRouter()


@router.post("/gen/start")
async def start_generation(url: str, db: AsyncSession = Depends(get_db)):
    # TODO: URL 유효성 검사 (지원 플랫폼 확인)
    # TODO: UUID job_id 생성 후 Job DB에 저장
    # TODO: BackgroundTask로 GenerationService.run_pipeline() 실행
    # TODO: job_id 즉시 반환
    # 반환 예시: {"job_id": "uuid-..."}
    raise NotImplementedError


@router.get("/gen/status/{job_id}")
async def get_generation_status(job_id: str, db: AsyncSession = Depends(get_db)):
    # TODO: SSE(text/event-stream) 스트림 반환
    # progress 이벤트: data: {"step": "crawling", "progress": 5}
    # complete 이벤트: data: {"glb_url": "...", "dimensions": {"w":..,"h":..,"d":..}}
    # error   이벤트: data: {"message": "크롤링 실패: ..."}
    raise NotImplementedError
