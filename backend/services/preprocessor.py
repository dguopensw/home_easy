"""배경 제거 및 인페인팅 서비스.

실제 구현은 pipeline_core.generate_sam3_furniture_mask / inpaint_obstacles_with_lama 참고.
"""

from pathlib import Path

from services.pipeline_core import (
    generate_sam3_furniture_mask as _generate_mask,
    inpaint_obstacles_with_lama as _inpaint,
    analyze_major_obstacles as _analyze_obstacles,
    segment_objects_with_sam3 as _segment_objects,
)


async def remove_background(image_path: str | Path, furniture_type: str = "unknown") -> Path:
    """SAM3 기반으로 가구 배경을 제거하고 마스크 경로를 반환합니다.

    Args:
        image_path: 원본 이미지 경로
        furniture_type: 가구 유형 (sofa, desk, chair 등)

    Returns:
        생성된 마스크 파일 경로
    """
    image_path = Path(image_path)
    mask_path = image_path.parent / "04_final_mask.png"

    result = _generate_mask(
        image_path=image_path,
        furniture_type=furniture_type,
        output_mask_path=mask_path,
    )

    if result["status"] != "done":
        raise RuntimeError(f"배경 제거 실패: {result.get('error')}")

    return mask_path


async def inpaint(image_path: str | Path, mask_path: str | Path) -> Path:
    """마스크 영역을 LaMa 인페인팅으로 채웁니다.

    Args:
        image_path: 원본 이미지 경로
        mask_path: 인페인팅할 마스크 경로

    Returns:
        인페인팅된 이미지 경로
    """
    image_path = Path(image_path)
    mask_path = Path(mask_path)
    output_path = image_path.parent / "05_inpainted.png"

    result = _inpaint(image_path, mask_path, output_path)

    if result["status"] != "done":
        raise RuntimeError(f"인페인팅 실패: {result.get('method')}")

    return output_path
