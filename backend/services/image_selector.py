"""이미지 선택 서비스: GPT-4o Vision으로 최적 이미지를 추천합니다."""
from __future__ import annotations

import json
import logging

from core import _core

logger = logging.getLogger(__name__)

_CONFIDENCE_VALUES = {"high", "medium", "low", "unknown"}


def _default_product_candidate_hint(reason: str = "") -> dict:
    return {
        "possible_brands": [],
        "possible_models": [],
        "brand_confidence": "unknown",
        "model_confidence": "unknown",
        "visual_features": [],
        "distinctive_parts": [],
        "search_keywords": [],
        "reason": reason,
    }


def _safe_string_list(value, max_items: int = 10) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value[:max_items]:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned:
                result.append(cleaned)
    return result


def _safe_confidence(value) -> str:
    if not isinstance(value, str):
        return "unknown"
    normalized = value.strip().lower()
    return normalized if normalized in _CONFIDENCE_VALUES else "unknown"


def _sanitize_product_candidate_hint(value) -> dict:
    if not isinstance(value, dict):
        return _default_product_candidate_hint("product candidate hint missing")

    return {
        "possible_brands": _safe_string_list(value.get("possible_brands")),
        "possible_models": _safe_string_list(value.get("possible_models")),
        "brand_confidence": _safe_confidence(value.get("brand_confidence")),
        "model_confidence": _safe_confidence(value.get("model_confidence")),
        "visual_features": _safe_string_list(value.get("visual_features")),
        "distinctive_parts": _safe_string_list(value.get("distinctive_parts")),
        "search_keywords": _safe_string_list(value.get("search_keywords")),
        "reason": value.get("reason", "") if isinstance(value.get("reason"), str) else "",
    }


class ImageSelectorService:
    def choose_best_image(self, title: str, description: str, image_urls: list[str]) -> dict:
        """GPT-4o Vision으로 이미지를 순위 매기고 최적 이미지를 추천합니다."""
        if not image_urls:
            raise ValueError("이미지가 없습니다.")

        default = {
            "recommended_index": 0,
            "ranked_candidate_indices": list(range(len(image_urls))),
            "reasoning": {},
            "product_candidate_hint": _default_product_candidate_hint(),
        }

        if len(image_urls) == 1:
            default["reasoning"] = {0: "only one image available"}
            default["product_candidate_hint"] = _default_product_candidate_hint(
                "only one image available; GPT product hint not extracted"
            )
            return default

        skip = _core._openai_skip_reason()
        if skip:
            default["reasoning"] = {0: f"GPT unavailable: {skip}"}
            default["product_candidate_hint"] = _default_product_candidate_hint(
                f"GPT unavailable: {skip}"
            )
            return default

        client = _core.get_openai_client()
        n = min(len(image_urls), 8)

        image_content: list[dict] = []
        for i, url in enumerate(image_urls[:n]):
            image_content.append({"type": "text", "text": f"[Image {i}]"})
            image_content.append({"type": "image_url", "image_url": {"url": url, "detail": "low"}})

        prompt = (
            f"Title: {title}\nDescription: {description[:400]}\n\n"
            f"Rank these {n} furniture images from best to worst for automated processing.\n"
            "Best = shows full furniture clearly, good angle, minimal occlusion, not too close-up.\n"
            "Also inspect the recommended image only and extract product matching candidate hints.\n"
            "Do NOT estimate dimensions.\n"
            "Do NOT assert or confirm a brand/model. Only provide candidates useful for later search.\n"
            "Use empty possible_brands/possible_models and confidence='unknown' if uncertain.\n"
            "Look for logos, labels, unique design, drawer count, handle style, leg shape, color, material, and structure.\n"
            "Search keywords should be text queries for product matching, not final conclusions.\n"
            "Return ONLY valid JSON:\n"
            "{"
            '"ranked": [0,1,2], '
            '"reasons": {"0": "reason", "1": "reason"}, '
            '"product_candidate_hint": {'
            '"possible_brands": [], '
            '"possible_models": [], '
            '"brand_confidence": "high|medium|low|unknown", '
            '"model_confidence": "high|medium|low|unknown", '
            '"visual_features": [], '
            '"distinctive_parts": [], '
            '"search_keywords": [], '
            '"reason": ""'
            "}"
            "}"
        )

        try:
            resp = client.chat.completions.create(
                model=_core.VISION_MODEL,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                ] + image_content}],
                max_tokens=700,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            _core._mark_openai_unavailable(e)
            logger.warning("Image ranking failed: %s", e)
            default["product_candidate_hint"] = _default_product_candidate_hint(
                "GPT image ranking failed"
            )
            return default

        try:
            parsed = json.loads(resp.choices[0].message.content.strip())
            ranked_raw = parsed.get("ranked", list(range(n)))
            reasons: dict[int, str] = {}
            if isinstance(parsed.get("reasons"), dict):
                for key, value in parsed["reasons"].items():
                    try:
                        reason_index = int(key)
                    except (TypeError, ValueError):
                        continue
                    if isinstance(value, str):
                        reasons[reason_index] = value

            ranked: list[int] = []
            if isinstance(ranked_raw, list):
                for raw_index in ranked_raw:
                    try:
                        index = int(raw_index)
                    except (TypeError, ValueError):
                        continue
                    if 0 <= index < len(image_urls):
                        ranked.append(index)

            seen = set(ranked)
            for i in range(len(image_urls)):
                if i not in seen:
                    ranked.append(i)

            return {
                "recommended_index": ranked[0],
                "ranked_candidate_indices": ranked,
                "reasoning": reasons,
                "product_candidate_hint": _sanitize_product_candidate_hint(
                    parsed.get("product_candidate_hint")
                ),
            }
        except Exception as e:
            logger.warning("Image ranking JSON parse failed: %s", e)
            default["product_candidate_hint"] = _default_product_candidate_hint(
                "GPT response JSON parse failed"
            )
            return default

    async def select(self, image_urls: list[str]) -> str:
        """기존 인터페이스 호환용. 추천 이미지 URL을 반환합니다."""
        result = self.choose_best_image("", "", image_urls)
        idx = result["recommended_index"]
        return image_urls[idx]
