"""스크래핑 서비스: 당근마켓 / 중고나라 URL에서 상품 정보를 수집합니다."""
from __future__ import annotations

import re

from core import _core


_APPROX_WORDS = re.compile(r'약|대략|정도|쯤')


def _has_approx(text: str) -> bool:
    return bool(_APPROX_WORDS.search(text))


class CrawlingService:
    # ── 스크래핑 ──────────────────────────────────────────────────────────

    def scrape_listing(self, url: str) -> dict:
        """당근마켓 또는 중고나라 상품 페이지를 스크래핑합니다."""
        normalized_url = _core.extract_listing_url(url)
        platform = _core.identify_platform(normalized_url)
        if not platform:
            raise ValueError("당근마켓 또는 중고나라 URL만 지원합니다.")
        scrapers = {"daangn": _core.scrape_daangn, "joongna": _core.scrape_joongna}
        data = scrapers[platform](normalized_url)
        data.setdefault("url", normalized_url)
        data["platform"] = platform
        return data

    def parse_listing_dimensions(self, title: str, description: str) -> dict | None:
        """판매글 제목·설명에서 치수(cm)를 추출합니다."""
        text = f"{title} {description}"

        # W x D x H (영문 표기): W120xD80xH75, W120*D80*H75
        m = re.search(
            r'[Ww][\s:]*(\d+\.?\d*)\s*[*xX×]\s*[Dd][\s:]*(\d+\.?\d*)\s*[*xX×]\s*[Hh][\s:]*(\d+\.?\d*)',
            text,
        )
        if m:
            return {
                "width_cm": float(m.group(1)),
                "depth_cm": float(m.group(2)),
                "height_cm": float(m.group(3)),
                "source": "listing_text",
                "pattern": "WxDxH",
                "approximate": _has_approx(m.group(0)),
                "raw_match": m.group(0),
            }

        # "가로세로 약 110cm 높이는 약 40cm" — 정사각형 평면 + 높이
        m = re.search(
            r'가로\s*세로\s*(?:약|대략|정도|쯤)?\s*(\d+\.?\d*)\s*(?:cm|CM)?\s*'
            r'높이\s*(?:는|은|가|이)?\s*(?:약|대략|정도|쯤)?\s*(\d+\.?\d*)\s*(?:cm|CM)?',
            text,
        )
        if m:
            side = float(m.group(1))
            return {
                "width_cm": side,
                "depth_cm": side,
                "height_cm": float(m.group(2)),
                "source": "listing_text",
                "pattern": "korean_galoselo_height",
                "approximate": _has_approx(m.group(0)),
                "raw_match": m.group(0),
            }

        # 한글 키워드 (가로, 세로, 높이 개별)
        found: dict[str, float] = {}
        approx_found = False
        kw_patterns = [
            (r'(?:가로|폭|너비)\s*(?:약|대략|정도|쯤)?\s*:?\s*(\d+\.?\d*)\s*(?:cm|CM)?', "width_cm"),
            (r'(?:세로|깊이)\s*(?:약|대략|정도|쯤)?\s*:?\s*(\d+\.?\d*)\s*(?:cm|CM)?', "depth_cm"),
            (r'(?:높이)\s*(?:는|은|가|이)?\s*(?:약|대략|정도|쯤)?\s*:?\s*(\d+\.?\d*)\s*(?:cm|CM)?', "height_cm"),
        ]
        for pattern, key in kw_patterns:
            m = re.search(pattern, text)
            if m:
                found[key] = float(m.group(1))
                if _has_approx(m.group(0)):
                    approx_found = True

        if len(found) >= 2:
            dims: dict = {"width_cm": None, "depth_cm": None, "height_cm": None}
            dims.update(found)
            return {**dims, "source": "listing_text", "pattern": "korean_keywords",
                    "approximate": approx_found}

        # 범용 NxNxN 패턴 (최후 수단)
        m = re.search(
            r'(\d+\.?\d*)\s*[*xX×]\s*(\d+\.?\d*)\s*[*xX×]\s*(\d+\.?\d*)\s*(?:cm|CM|mm|MM)?',
            text,
        )
        if m:
            v1, v2, v3 = float(m.group(1)), float(m.group(2)), float(m.group(3))
            if max(v1, v2, v3) > 500:  # mm → cm 변환
                v1, v2, v3 = v1 / 10, v2 / 10, v3 / 10
            return {
                "width_cm": v1, "depth_cm": v2, "height_cm": v3,
                "source": "listing_text", "pattern": "NxNxN",
                "approximate": _has_approx(m.group(0)),
                "raw_match": m.group(0),
            }

        return None

    async def crawl(self, url: str) -> dict:
        """기존 인터페이스 호환용. 스크래핑 후 image_urls / text / platform 반환."""
        data = self.scrape_listing(url)
        return {
            "image_urls": data.get("images", []),
            "text": data.get("description", ""),
            "platform": data.get("platform", ""),
            "title": data.get("title", ""),
        }
