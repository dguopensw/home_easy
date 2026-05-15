import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from services.crawling_service import CrawlingService
from services.image_selector import ImageSelectorService
from services.preprocessor import PreprocessorService
from services.dimension_estimator import DimensionEstimatorService


class GenerationService:
    def __init__(self):
        self.crawling = CrawlingService()
        self.image_selector = ImageSelectorService()
        self.preprocessor = PreprocessorService()
        self.dimension_estimator = DimensionEstimatorService()

    def create_job_id(self) -> str:
        return str(uuid.uuid4())

    async def run_pipeline(self, job_id: str, source_url: str, db: AsyncSession):
        # TODO: 각 단계 실행 + SSE progress 이벤트 발행
        # 단계별 진행률:
        #   1. crawling.crawl(source_url)             →  0% →  5%
        #   2. image_selector.select(image_urls)      →  5% → 10%
        #   3. preprocessor.preprocess(image_url)     → 10% → 20%
        #   4. dimension_estimator.estimate(img_path) → 20% → 30%
        #   5. RunPod API POST /run 호출              → 30% 시작
        #   6. poll_runpod(runpod_job_id)             → 30% → 95%
        #   7. DB 저장 + SSE complete 이벤트          → 100%
        # 에러 시: Job.status = "failed", SSE error 이벤트 발행
        raise NotImplementedError

    async def poll_runpod(self, runpod_job_id: str) -> str:
        # TODO: GET https://api.runpod.ai/v2/{ENDPOINT_ID}/status/{runpod_job_id}
        # TODO: 2초 간격 폴링, 완료 시 glb_url 반환
        # 반환: glb_url (S3 URL)
        raise NotImplementedError
