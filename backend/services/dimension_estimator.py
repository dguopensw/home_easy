"""가구 치수 추정 서비스."""

from pathlib import Path
from typing import Any


async def estimate_dimensions(image_path: str | Path, title: str = "", description: str = "") -> dict[str, float]:
    """가구 이미지에서 치수(w, h, d)를 추정합니다.

    Args:
        image_path: 전처리된 가구 이미지 경로
        title: 게시글 제목 (치수 힌트 추출용)
        description: 게시글 설명 (치수 힌트 추출용)

    Returns:
        {"w": float, "h": float, "d": float}  # 단위: cm

    TODO: GPT-4o Vision + 픽셀 비율 기반 치수 추정 구현
          참고: pipeline_GPT/app.py 의 dimension estimation 로직
    """
    raise NotImplementedError("estimate_dimensions 미구현")
