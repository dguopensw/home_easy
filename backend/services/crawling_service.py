class CrawlingService:
    async def crawl(self, url: str) -> dict:
        # TODO: 플랫폼 감지 (당근마켓 / 번개장터 / 중고나라)
        # TODO: 지원하지 않는 플랫폼이면 ValueError 발생
        # TODO: Playwright로 JS 렌더링 후 이미지 URL 목록 + 게시글 텍스트 수집
        # 반환: {"image_urls": ["https://..."], "text": "...", "platform": "daangn"}
        raise NotImplementedError
