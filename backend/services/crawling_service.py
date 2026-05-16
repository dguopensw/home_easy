"""플랫폼별 크롤링 서비스.

당근, 번개장터 등 중고거래 플랫폼에서 게시글 정보(제목, 설명, 이미지 URL 목록)를 가져옵니다.
굳이 안 채워도 됩니다 — 필요 시 구현하세요.
"""

from typing import Any


async def crawl_listing(url: str) -> dict[str, Any]:
    """URL에서 게시글 정보를 크롤링합니다.

    Returns:
        {
            "title": str,
            "description": str,
            "image_urls": list[str],
        }

    TODO: 플랫폼(당근 / 번개장터 / 중고나라 등)을 감지하고 각각 파싱 로직 구현
    """
    raise NotImplementedError("crawl_listing 미구현")
