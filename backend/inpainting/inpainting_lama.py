"""LaMa(in-process) 인페인팅 — 시도 1(SAM + LaMa) 재현용.

이 모듈은 LaMa로 마스크 영역을 채운 **원본(raw) 결과**를 그대로 저장한다.
BrushNet 합성을 적용하지 않으므로, 가구 표면처럼 넓고 일관된 텍스처를 채울 때
LaMa 특유의 흐릿(blur)한 출력이 그대로 드러난다 — 이는 보고서 '시도 1'의
인페인팅 품질 한계를 발표 자료용 이미지로 시연하기 위한 의도된 동작이다.

CPU/GPU 자동 감지(SimpleLama 내부)로 동작하며, 로컬 macOS(CPU)에서도 실행된다.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_lama = None


def _get_lama():
    """SimpleLama 싱글턴 — 모델 로딩(~12s, 최초 1회)을 재사용한다."""
    global _lama
    if _lama is None:
        from simple_lama_inpainting import SimpleLama

        logger.info("Loading LaMa (big-lama) model...")
        _lama = SimpleLama()
        logger.info("LaMa model loaded.")
    return _lama


def inpaint_with_lama(
    image_path: Path,
    mask_path: Path,
    output_path: Path,
    mask_dilation_px: int = 0,
    composite: bool = False,
) -> dict:
    """LaMa로 마스크 영역을 인페인팅한다 (시도 1 재현).

    Args:
        image_path: 원본 이미지
        mask_path: 인페인팅 대상(흰색=채울 영역) 마스크
        output_path: 결과 저장 경로
        mask_dilation_px: >0이면 마스크를 확장해 그림자/경계까지 포함
        composite: True면 마스크 내부만 LaMa 결과로 교체(가구 본체 보존),
                   False(기본)면 LaMa 원본 출력을 그대로 저장 — blur 시연용

    Returns:
        status/method/warnings/diagnostics 딕셔너리
    """
    import numpy as np
    from PIL import Image, ImageFilter

    BASE_WARNINGS = [
        "inpainting_used",
        "lama_raw_output_may_be_blurry",
        "not_for_measurement",
    ]

    try:
        lama = _get_lama()

        image = Image.open(image_path).convert("RGB")
        mask = Image.open(mask_path).convert("L")
        w, h = image.size

        if mask.size != image.size:
            mask = mask.resize((w, h), Image.NEAREST)

        # 마스크 이진화 (원본 — 합성/진단용)
        mask_arr = np.array(mask)
        mask_bin = (mask_arr > 127).astype(np.uint8) * 255
        original_mask = Image.fromarray(mask_bin, mode="L")
        coverage = float((mask_bin > 0).sum()) / (w * h)

        # LaMa 입력용 마스크 (선택적 dilation)
        lama_mask = original_mask
        if mask_dilation_px > 0:
            filter_size = max(3, mask_dilation_px * 2 + 1)
            if filter_size % 2 == 0:
                filter_size += 1
            lama_mask = lama_mask.filter(ImageFilter.MaxFilter(size=filter_size))

        # LaMa 추론 — 마스크 영역을 주변 컨텍스트로부터 추정해 채움
        result = lama(image, lama_mask)
        if result.size != (w, h):
            result = result.resize((w, h), Image.LANCZOS)

        if composite:
            # 마스크 내부만 LaMa 결과로 교체 (가구 본체 픽셀 보존)
            hard_mask = Image.fromarray(mask_bin, mode="L")
            composite_mask = hard_mask.filter(ImageFilter.GaussianBlur(radius=1.5))
            out = image.copy()
            out.paste(result, mask=composite_mask)
        else:
            # LaMa 원본 출력 그대로 — blur 한계 시연
            out = result

        output_path.parent.mkdir(parents=True, exist_ok=True)
        out.save(output_path)

        logger.info(
            "LaMa inpainting done: %dx%d, mask_coverage=%.3f, composite=%s",
            w, h, coverage, composite,
        )

        return {
            "status": "done",
            "method": "lama_raw" if not composite else "lama_brushnet_composite",
            "warnings": BASE_WARNINGS,
            "diagnostics": {
                "original_size": [w, h],
                "mask_coverage": round(coverage, 4),
                "mask_dilation_px": mask_dilation_px,
                "composite": composite,
            },
        }

    except Exception as e:
        logger.error("LaMa inpainting failed: %s", e)
        return {
            "status": "failed",
            "method": "lama_unavailable",
            "warnings": ["lama_inpainting_failed_fallback_to_original"],
            "error": str(e),
        }
