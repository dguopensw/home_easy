"""치수 추정 서비스: 판매글 텍스트 파싱 또는 GPT Vision으로 치수를 추정합니다."""
from __future__ import annotations

from pathlib import Path

from core import _core


class DimensionEstimatorService:
    def estimate_dimensions(
        self,
        measurement_image_path: Path,
        title: str,
        description: str,
        furniture_type: str,
        listing_dims: dict | None,
    ) -> dict:
        """치수를 추정합니다. 판매글 텍스트 우선, 실패 시 Vision 추정."""
        if listing_dims and listing_dims.get("width_cm"):
            is_approx = bool(listing_dims.get("approximate", False))
            return {
                "width_cm": listing_dims["width_cm"],
                "depth_cm": listing_dims.get("depth_cm"),
                "height_cm": listing_dims.get("height_cm"),
                "source": "listing_text",
                "confidence": "high",
                "approximate": is_approx,
                "pattern": listing_dims.get("pattern"),
                "raw_match": listing_dims.get("raw_match"),
                "reasoning": (
                    "Dimensions extracted from listing text (approximate)."
                    if is_approx else
                    "Dimensions extracted directly from listing text."
                ),
            }

        dims = _core.measure_dimensions(
            measurement_image_path,
            title,
            description,
            furniture_type=furniture_type,
        )
        dims.setdefault("source", "vision_estimate")
        return dims

    async def estimate(self, image_path: str) -> dict:
        """기존 인터페이스 호환용."""
        dims = _core.measure_dimensions(Path(image_path), "", "", furniture_type="unknown")
        return {
            "w": dims.get("width_cm"),
            "h": dims.get("height_cm"),
            "d": dims.get("depth_cm"),
        }
