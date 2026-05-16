"""GET /furniture/crawl/test — 크롤링 테스트 (개발용)."""

from fastapi import APIRouter
from pydantic import BaseModel

from services.crawling_service import crawl_listing

router = APIRouter()


class CrawlRequest(BaseModel):
    url: str


@router.get("/test")
async def test_crawl(url: str):
    result = await crawl_listing(url)
    return result
