"""Flux-Fill + BrushNet-style compositing inpainting."""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_pipe = None


def _get_pipe():
    global _pipe
    if _pipe is None:
        import torch
        from diffusers import FluxFillPipeline

        logger.info("Loading FLUX.1-Fill-dev model...")
        _pipe = FluxFillPipeline.from_pretrained(
            "black-forest-labs/FLUX.1-Fill-dev",
            torch_dtype=torch.bfloat16,
        ).to("cuda")
        logger.info("FLUX.1-Fill-dev loaded.")
    return _pipe


def inpaint_with_flux(
    image_path: Path,
    mask_path: Path,
    output_path: Path,
    prompt: str = "",
    num_inference_steps: int = 28,
    guidance_scale: float = 30.0,
) -> dict:
    """Flux-Fill 인페인팅 후 BrushNet 스타일로 원본에 합성합니다.

    1. Flux-Fill: 원본 이미지 + 마스크 → 마스크 영역 인페인팅
    2. BrushNet composite: 마스크 내부만 Flux 결과로 교체, 나머지는 원본 유지
    """
    from PIL import Image

    BASE_WARNINGS = [
        "inpainting_used",
        "generation_uses_inpainted_image",
        "not_for_measurement",
    ]

    try:
        pipe = _get_pipe()

        image = Image.open(image_path).convert("RGB")
        mask = Image.open(mask_path).convert("L")
        w, h = image.size

        # Flux는 8의 배수 해상도 필요
        w8 = (w // 8) * 8
        h8 = (h // 8) * 8
        image_input = image.resize((w8, h8))
        mask_input = mask.resize((w8, h8))

        result = pipe(
            prompt=prompt,
            image=image_input,
            mask_image=mask_input,
            height=h8,
            width=w8,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
        ).images[0]

        # 원본 크기로 복원
        result = result.resize((w, h))

        # BrushNet compositing: 마스크 내부만 Flux 결과로, 나머지는 원본 유지
        composite = image.copy()
        composite.paste(result, mask=mask)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        composite.save(output_path)

        return {
            "status": "done",
            "method": "flux_fill_brushnet_composite",
            "warnings": BASE_WARNINGS,
        }

    except Exception as e:
        logger.error("Flux inpainting failed: %s", e)
        return {
            "status": "failed",
            "method": "flux_fill_unavailable",
            "warnings": ["flux_inpainting_failed_fallback_to_original"],
        }
