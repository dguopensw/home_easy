"""GPT-4o Vision을 사용해 가구 이미지 중 가장 적합한 이미지를 선정합니다."""

from typing import Any


async def select_best_image(image_urls: list[str], title: str = "", description: str = "") -> str:
    """이미지 목록에서 GPT-4o Vision으로 가장 적합한 가구 이미지 URL을 반환합니다.

    Args:
        image_urls: 크롤링된 이미지 URL 목록
        title: 게시글 제목
        description: 게시글 설명

    Returns:
        선택된 이미지 URL

    TODO: OpenAI GPT-4o Vision API 호출로 가구 이미지 선정 구현
          참고: pipeline_GPT/app.py 의 image selection 로직
    """
    raise NotImplementedError("select_best_image 미구현")
