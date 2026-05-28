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


_FURNITURE_PROMPTS: dict[str, str] = {
    "sofa":     "smooth continuous sofa upholstery fabric, plain unobstructed body surface, matching the existing sofa texture and color, photorealistic, consistent lighting with the rest of the scene",
    "chair":    "smooth continuous chair upholstery fabric, plain unobstructed body surface, matching the existing chair texture and color, photorealistic, consistent lighting",
    "desk":     "smooth continuous desk top surface, plain unobstructed, matching the existing desk wood material and color, photorealistic, consistent lighting",
    "table":    "smooth continuous table top surface, plain unobstructed, matching the existing table material and color, photorealistic, consistent lighting",
    "bed":      "smooth flat bed sheet surface, plain unobstructed bedding, matching the existing sheet texture and color, photorealistic, consistent lighting",
    "wardrobe": "smooth floor or wall behind wardrobe, matching the existing texture, photorealistic, consistent lighting",
    "drawer":   "smooth drawer front panel, plain unobstructed, matching the existing material and color, photorealistic, consistent lighting",
    "shelf":    "smooth empty shelf panel surface, plain unobstructed, matching the existing shelf texture and color, photorealistic, consistent lighting",
}

_DEFAULT_PROMPT = "smooth continuous furniture body surface, plain unobstructed, matching the surroundings, photorealistic, consistent lighting"


def _get_prompt(furniture_type: str) -> str:
    return _FURNITURE_PROMPTS.get(furniture_type.lower(), _DEFAULT_PROMPT)


def inpaint_with_flux(
    image_path: Path,
    mask_path: Path,
    output_path: Path,
    furniture_type: str = "",
    num_inference_steps: int = 50,
    guidance_scale: float = 30.0,
    mask_dilation_px: int = 15,
    seed: int = 42,
) -> dict:
    """Flux-Fill 인페인팅 후 BrushNet 스타일로 원본에 합성합니다.

    1. Mask preprocessing: 이진화 + dilation으로 객체 그림자/경계까지 포함
    2. Flux-Fill: 원본 이미지 + 마스크 → 마스크 영역 인페인팅
    3. BrushNet composite: hard mask로 마스크 내부만 Flux 결과로 교체
    """
    import numpy as np
    import torch
    from PIL import Image, ImageFilter

    BASE_WARNINGS = [
        "inpainting_used",
        "generation_uses_inpainted_image",
        "not_for_measurement",
    ]

    try:
        pipe = _get_pipe()
        prompt = _get_prompt(furniture_type)
        logger.info("Flux inpainting prompt: %s", prompt)

        image = Image.open(image_path).convert("RGB")
        mask = Image.open(mask_path).convert("L")
        w, h = image.size

        # 마스크 강제 이진화 (anti-aliasing/회색 픽셀 제거)
        mask_arr = np.array(mask)
        mask_bin = (mask_arr > 127).astype(np.uint8) * 255
        mask = Image.fromarray(mask_bin, mode="L")

        # Dilation: 객체 경계 + 그림자/잔상 영역까지 포함
        if mask_dilation_px > 0:
            # MaxFilter size는 홀수여야 하며 대략 2*radius+1
            filter_size = max(3, mask_dilation_px * 2 + 1)
            if filter_size % 2 == 0:
                filter_size += 1
            mask = mask.filter(ImageFilter.MaxFilter(size=filter_size))

        # Flux는 8의 배수 해상도 필요
        w8 = (w // 8) * 8
        h8 = (h // 8) * 8
        # 이미지: 고품질 LANCZOS, 마스크: NEAREST 후 재이진화로 hard edge 유지
        image_input = image.resize((w8, h8), Image.LANCZOS)
        mask_input = mask.resize((w8, h8), Image.NEAREST)
        mask_input_arr = np.array(mask_input)
        mask_input_arr = (mask_input_arr > 127).astype(np.uint8) * 255
        mask_input = Image.fromarray(mask_input_arr, mode="L")

        generator = torch.Generator(device="cuda").manual_seed(seed)

        result = pipe(
            prompt=prompt,
            image=image_input,
            mask_image=mask_input,
            height=h8,
            width=w8,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            generator=generator,
        ).images[0]

        # 원본 크기로 복원
        result = result.resize((w, h), Image.LANCZOS)

        # 합성용 hard mask (이진) + 가장자리만 살짝 부드럽게 (자연스러운 블렌딩)
        hard_mask_arr = (np.array(mask) > 127).astype(np.uint8) * 255
        hard_mask = Image.fromarray(hard_mask_arr, mode="L")
        # 1~2px 정도의 미세한 블러로 경계 자연스럽게
        composite_mask = hard_mask.filter(ImageFilter.GaussianBlur(radius=1.5))

        composite = image.copy()
        composite.paste(result, mask=composite_mask)

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
