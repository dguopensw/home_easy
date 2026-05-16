"""파이프라인 조합 + SSE 스트리밍.

전체 흐름 (pipeline_core.run_service_pipeline 기반):
    source_url
    → scrape_listing()                    # 이미지 URL 목록 수집 (당근/중고나라)
    → choose_best_image()                 # GPT-4o Vision으로 최적 이미지 선정
    → generate_sam3_furniture_mask()      # SAM3 기반 가구 마스크 생성
    → analyze_major_obstacles()           # GPT-4o 장애물 분석
    → analyze_generation_contaminants()   # GPT-4o 오염 요소 분석
    → (필요 시) inpaint_obstacles_with_lama()  # LaMa 인페인팅
    → estimate_dimensions()               # 치수 추정 (텍스트 우선, Vision 보조)
    → RunPod API 3D 생성 → S3 업로드     # TODO: RunPod 연결
    → DB 저장 → SSE complete 이벤트
"""

import json
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from services.pipeline_core import run_service_pipeline as _run_pipeline


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# job_id → (source_url, selected_image_index) 임시 저장소
# TODO: Redis 또는 DB 임시 테이블로 교체
_pending_jobs: dict[str, dict] = {}


def register_job(job_id: str, source_url: str, selected_image_index: int = 0) -> None:
    """start 엔드포인트에서 job 정보를 등록합니다."""
    _pending_jobs[job_id] = {
        "source_url": source_url,
        "selected_image_index": selected_image_index,
    }


async def run_pipeline_sse(job_id: str, db: AsyncSession) -> AsyncGenerator[str, None]:
    """파이프라인 전체를 실행하고 진행 상태를 SSE로 스트리밍합니다.

    에러 발생 시 DB에 저장하지 않고 error 이벤트만 전송합니다.
    완료 시 DB에 Job 저장 후 complete 이벤트를 전송합니다.
    """
    job_info = _pending_jobs.pop(job_id, None)
    if not job_info:
        yield _sse("error", {"message": f"job_id {job_id} 를 찾을 수 없습니다."})
        return

    source_url = job_info["source_url"]
    selected_image_index = job_info.get("selected_image_index", 0)

    try:
        yield _sse("progress", {"step": "pipeline_start", "message": "파이프라인 시작..."})

        # run_service_pipeline은 동기 함수 — 실제 서비스에서는 asyncio.to_thread로 감싸세요
        import asyncio
        result, status_code = await asyncio.to_thread(
            _run_pipeline, source_url, selected_image_index
        )

        if status_code != 200 or "error" in result:
            yield _sse("error", {"message": result.get("error", "파이프라인 실패")})
            return

        dimensions = result.get("dimensions", {})
        dims_formatted = {
            "w": dimensions.get("width_cm"),
            "h": dimensions.get("height_cm"),
            "d": dimensions.get("depth_cm"),
        }

        # TODO: RunPod API로 3D 모델 생성 요청 + S3 업로드
        yield _sse("progress", {"step": "generation", "message": "3D 모델 생성 중 (RunPod)..."})
        glb_url = ""  # TODO: RunPod 결과 GLB S3 URL

        # TODO: DB에 Job 저장
        # from models.job import Job
        # job = Job(job_id=job_id, source_url=source_url, dimensions=dims_formatted, glb_url=glb_url)
        # db.add(job)
        # await db.commit()

        yield _sse("complete", {
            "job_id": job_id,
            "dimensions": dims_formatted,
            "glb_url": glb_url,
            "pipeline_result": result,
        })

    except Exception as e:
        yield _sse("error", {"message": str(e)})
