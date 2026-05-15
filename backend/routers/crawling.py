from fastapi import APIRouter

router = APIRouter()


@router.get("/crawl/test")
async def test_crawl(url: str):
    # TODO: CrawlingService.crawl(url) 호출 후 결과 반환 (개발용 테스트 엔드포인트)
    raise NotImplementedError
