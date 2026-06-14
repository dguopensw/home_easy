from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core import _core
from services.crawling_service import CrawlingService
from services.image_selector import ImageSelectorService
from services.scrape_store import scrape_store

router = APIRouter()
_crawling = CrawlingService()
_image_selector = ImageSelectorService()


class ScrapeRequest(BaseModel):
    url: str = ""


@router.post("/scrape")
def api_scrape(body: ScrapeRequest):
    """URL 스크래핑 및 이미지 순위 추천."""
    url = _core.extract_listing_url(body.url)
    if not url:
        raise HTTPException(status_code=400, detail="URL을 입력해주세요.")

    platform = _core.identify_platform(url)
    if not platform:
        raise HTTPException(status_code=400, detail="당근마켓 또는 중고나라 URL만 지원합니다.")

    try:
        scraped = _crawling.scrape_listing(url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스크래핑 실패: {e}")

    image_urls = scraped.get("images", [])
    title = scraped.get("title", "")
    description = scraped.get("description", "")
    source_url = scraped.get("url") or url

    image_ranking = _image_selector.choose_best_image(title, description, image_urls)
    listing_dims = _crawling.parse_listing_dimensions(title, description)
    listing_class = _core.classify_furniture_from_listing(title, description)

    store_data = {
        "url": source_url,
        "title": title,
        "description": description,
        "price": scraped.get("price", ""),
        "platform": scraped.get("platform", ""),
        "images": image_urls,
        "image_urls": image_urls,
        "ai_recommended_image_index": image_ranking["recommended_index"],
        "ranked_candidate_indices": image_ranking["ranked_candidate_indices"],
        "image_reasoning": image_ranking.get("reasoning", {}),
        "furniture_guess": {
            "type": listing_class["furniture_type"],
            "confidence": listing_class["confidence"],
        },
        "dimensions_from_listing": listing_dims,
    }
    scrape_id = scrape_store.create(store_data)

    return JSONResponse(content={
        "scrape_id": scrape_id,
        "title": title,
        "description": description,
        "price": scraped.get("price", ""),
        "platform": scraped.get("platform", ""),
        "url": source_url,
        "image_urls": image_urls,
        "ai_recommended_image_index": image_ranking["recommended_index"],
        "ranked_candidate_indices": image_ranking["ranked_candidate_indices"],
        "image_reasoning": {str(k): v for k, v in image_ranking.get("reasoning", {}).items()},
        "furniture_guess": {
            "type": listing_class["furniture_type"],
            "confidence": listing_class["confidence"],
        },
        "dimensions_from_listing": listing_dims,
    })


@router.get("/crawl/test")
async def test_crawl(url: str):
    """크롤링 테스트 엔드포인트 (개발용)."""
    result = await _crawling.crawl(url)
    return result
