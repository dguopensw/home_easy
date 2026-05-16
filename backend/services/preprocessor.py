"""배경 제거 및 인페인팅 서비스."""

from pathlib import Path
from typing import Any


async def remove_background(image_path: str | Path) -> Path:
    """이미지에서 배경을 제거하고 컷아웃 이미지 경로를 반환합니다.

    TODO: BiRefNet 또는 SAM 기반 배경 제거 구현
          참고: pipeline_GPT/clean_pipeline.py, service_pipeline.py
    """
    raise NotImplementedError("remove_background 미구현")


async def inpaint(image_path: str | Path, mask_path: str | Path) -> Path:
    """마스크 영역을 LaMa 인페인팅으로 채웁니다.

    TODO: LaMa 인페인팅 모델 호출 구현
          참고: pipeline_GPT/lama_inpaint_worker.py
    """
    raise NotImplementedError("inpaint 미구현")
