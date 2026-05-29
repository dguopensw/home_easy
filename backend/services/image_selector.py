"""이미지 선택 서비스: GPT-4o Vision으로 최적 이미지를 추천합니다."""
from __future__ import annotations

import json
import logging

from core import _core

logger = logging.getLogger(__name__)


class ImageSelectorService:
    def choose_best_image(self, title: str, description: str, image_urls: list[str]) -> dict:
        """GPT-4o Vision으로 이미지를 순위 매기고 최적 이미지를 추천합니다."""
        if not image_urls:
            raise ValueError("이미지가 없습니다.")

        default = {
            "recommended_index": 0,
            "ranked_candidate_indices": list(range(len(image_urls))),
            "reasoning": {},
        }

        if len(image_urls) == 1:
            default["reasoning"] = {0: "only one image available"}
            return default

        skip = _core._openai_skip_reason()
        if skip:
            default["reasoning"] = {0: f"GPT unavailable: {skip}"}
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
            "Return ONLY valid JSON:\n"
            '{"ranked": [0,1,2,...], "reasons": {"0": "reason", "1": "reason"}}'
        )

        try:
            resp = client.chat.completions.create(
                model=_core.VISION_MODEL,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                ] + image_content}],
                max_tokens=300,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(resp.choices[0].message.content.strip())
            ranked_raw = parsed.get("ranked", list(range(n)))
            reasons = {int(k): v for k, v in parsed.get("reasons", {}).items()}

            ranked = [int(i) for i in ranked_raw if 0 <= int(i) < len(image_urls)]
            seen = set(ranked)
            for i in range(len(image_urls)):
                if i not in seen:
                    ranked.append(i)

            return {
                "recommended_index": ranked[0],
                "ranked_candidate_indices": ranked,
                "reasoning": reasons,
            }
        except Exception as e:
            _core._mark_openai_unavailable(e)
            logger.warning("Image ranking failed: %s", e)
            return default

    async def select(self, image_urls: list[str]) -> str:
        """기존 인터페이스 호환용. 추천 이미지 URL을 반환합니다."""
        result = self.choose_best_image("", "", image_urls)
        idx = result["recommended_index"]
        return image_urls[idx]
