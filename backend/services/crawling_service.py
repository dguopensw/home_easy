"""플랫폼별 크롤링 서비스.

당근, 중고나라 등 중고거래 플랫폼에서 게시글 정보(제목, 설명, 이미지 URL 목록)를 가져옵니다.
실제 구현은 pipeline_core.scrape_listing 참고.
"""

from typing import Any

from services.pipeline_core import scrape_listing as _scrape_listing


async def crawl_listing(url: str) -> dict[str, Any]:
    """URL에서 게시글 정보를 크롤링합니다.

    Returns:
        {
            "title": str,
            "description": str,
            "images": list[str],
            "price": str,
            "platform": str,
        }
    """
    return _scrape_listing(url)
