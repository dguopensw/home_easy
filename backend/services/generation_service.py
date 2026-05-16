"""파이프라인 조합 + RunPod 폴링 + SSE 스트리밍.

전체 흐름:
    source_url
    → crawling_service.crawl_listing()       # 이미지 URL 목록 수집
    → image_selector.select_best_image()     # GPT-4o Vision으로 최적 이미지 선정
    → preprocessor.remove_background()       # 배경 제거
    → dimension_estimator.estimate_dimensions()  # 치수 추정
    → RunPod API로 3D 모델 생성 요청 + 폴링
    → S3 업로드 → DB 저장
    → SSE complete 이벤트 전송
"""

import asyncio
import json
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from services.crawling_service import crawl_listing
from services.image_selector import select_best_image
from services.preprocessor import remove_background
from services.dimension_estimator import estimate_dimensions


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def run_pipeline_sse(job_id: str, db: AsyncSession) -> AsyncGenerator[str, None]:
    """파이프라인 전체를 실행하고 진행 상태를 SSE로 스트리밍합니다.

    에러 발생 시 DB에 저장하지 않고 error 이벤트만 전송합니다.

    TODO: 아래 단계별 TODO를 순서대로 구현하세요.
          전체 흐름은 docs/feature-flow/request-flow.md 참고 + 다후님 설계변경 사항에 맞게 구현.
    """
    try:
        # TODO 1: job_id에 매핑된 source_url을 가져옵니다 (메모리 캐시 또는 임시 테이블 활용)
        source_url = ""

        yield _sse("progress", {"step": "crawling", "message": "게시글 크롤링 중..."})
        # TODO 2: crawl_listing(source_url) 호출
        listing = await crawl_listing(source_url)

        yield _sse("progress", {"step": "image_select", "message": "최적 이미지 선정 중..."})
        # TODO 3: select_best_image(listing["image_urls"], ...) 호출
        image_url = await select_best_image(listing["image_urls"], listing.get("title", ""))

        yield _sse("progress", {"step": "preprocess", "message": "배경 제거 중..."})
        # TODO 4: 이미지 다운로드 후 remove_background() 호출
        cutout_path = await remove_background(image_url)

        yield _sse("progress", {"step": "dimension", "message": "치수 추정 중..."})
        # TODO 5: estimate_dimensions() 호출
        dimensions = await estimate_dimensions(cutout_path, listing.get("title", ""))

        yield _sse("progress", {"step": "generation", "message": "3D 모델 생성 중 (RunPod)..."})
        # TODO 6: RunPod API로 3D 생성 요청 → 폴링으로 완료 대기
        glb_url = ""  # TODO: RunPod 결과 GLB S3 URL

        # TODO 7: DB에 Job 저장
        # job = Job(job_id=job_id, source_url=source_url, dimensions=dimensions, glb_url=glb_url)
        # db.add(job)
        # await db.commit()

        yield _sse("complete", {"job_id": job_id, "dimensions": dimensions, "glb_url": glb_url})

    except Exception as e:
        yield _sse("error", {"message": str(e)})
