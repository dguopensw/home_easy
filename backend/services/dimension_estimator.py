"""가구 치수 추정 서비스.

실제 구현은 pipeline_core.parse_listing_dimensions / estimate_dimensions 참고.
"""

from pathlib import Path

from services.pipeline_core import (
    parse_listing_dimensions as _parse_listing_dims,
    estimate_dimensions as _estimate_dimensions,
)


async def estimate_dimensions(
    image_path: str | Path,
    title: str = "",
    description: str = "",
    furniture_type: str = "unknown",
) -> dict[str, float]:
    """가구 이미지에서 치수(w, h, d)를 추정합니다.

    게시글 텍스트에 치수가 있으면 텍스트 우선, 없으면 Vision 모델로 추정합니다.

    Returns:
        {"width_cm": float, "depth_cm": float, "height_cm": float, "source": str, ...}
    """
    listing_dims = _parse_listing_dims(title, description)
    return _estimate_dimensions(
        measurement_image_path=Path(image_path),
        title=title,
        description=description,
        furniture_type=furniture_type,
        listing_dims=listing_dims,
    )
