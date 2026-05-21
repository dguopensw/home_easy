"""GenerationService: PipelineService로 위임하는 호환 레이어."""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from services.pipeline_service import PipelineService

_pipeline = PipelineService()


class GenerationService:
    def __init__(self):
        self._pipeline = _pipeline

    def create_job_id(self) -> str:
        return str(uuid.uuid4())

    async def run_pipeline(self, job_id: str, source_url: str, db: AsyncSession):
        """PipelineService로 위임합니다."""
        result, _ = self._pipeline.run_pipeline(source_url, 0)
        return result

    async def poll_runpod(self, runpod_job_id: str) -> str:
        raise NotImplementedError
