"""GPT-4o Vision을 사용해 가구 이미지 중 가장 적합한 이미지를 선정합니다.

실제 구현은 pipeline_core.choose_best_image 참고.
"""

from services.pipeline_core import choose_best_image as _choose_best_image


async def select_best_image(image_urls: list[str], title: str = "", description: str = "") -> str:
    """이미지 목록에서 GPT-4o Vision으로 가장 적합한 가구 이미지 URL을 반환합니다.

    Args:
        image_urls: 크롤링된 이미지 URL 목록
        title: 게시글 제목
        description: 게시글 설명

    Returns:
        선택된 이미지 URL
    """
    result = _choose_best_image(title, description, image_urls)
    idx = result["recommended_index"]
    return image_urls[idx]
