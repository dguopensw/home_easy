"""Nano Banana (Gemini) + BrushNet-style compositing inpainting."""
from __future__ import annotations

import io
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is not set")
        _client = genai.Client(api_key=api_key)
        logger.info("Gemini (Nano Banana) client initialized.")
    return _client


_FURNITURE_PROMPTS: dict[str, str] = {
    "sofa":     "Fill the blank white area naturally with empty sofa cushions. Match the existing upholstery texture, color, and lighting. Do not add any objects.",
    "chair":    "Fill the blank white area naturally with an empty chair seat surface. Match the existing fabric texture, color, and lighting. Do not add any objects.",
    "desk":     "Fill the blank white area naturally with an empty desk surface. Match the existing wood texture, color, and lighting. Do not add any objects.",
    "table":    "Fill the blank white area naturally with an empty table surface. Match the existing material, color, and lighting. Do not add any objects.",
    "bed":      "Fill the blank white area naturally with smooth flat bedding. Match the existing sheet texture, color, and lighting. Do not add any objects.",
    "wardrobe": "Fill the blank white area naturally with the floor or wall behind. Match the existing texture, color, and lighting. Do not add any objects.",
    "drawer":   "Fill the blank white area naturally with a smooth drawer front surface. Match the existing material, color, and lighting. Do not add any objects.",
    "shelf":    "Fill the blank white area naturally with an empty shelf surface. Match the existing texture, color, and lighting. Do not add any objects.",
}

_DEFAULT_PROMPT = "Fill the blank white area naturally with a clean surface that matches the surrounding furniture texture, color, and lighting. Do not add any objects."

_MODEL = os.environ.get("NANO_BANANA_MODEL", "gemini-3-pro-image-preview")


def _get_prompt(furniture_type: str) -> str:
    return _FURNITURE_PROMPTS.get(furniture_type.lower(), _DEFAULT_PROMPT)


def inpaint_with_banana(
    image_path: Path,
    mask_path: Path,
    output_path: Path,
    furniture_type: str = "",
    mask_dilation_px: int = 15,
) -> dict:
    """Nano Banana 인페인팅 후 BrushNet 스타일로 원본에 합성합니다.

    1. Mask preprocessing: 이진화 + dilation으로 객체 그림자/경계까지 포함
    2. 힌트 이미지 생성: 마스크 영역을 흰색으로 칠해 편집 영역 표시
    3. Nano Banana API: 힌트 이미지 + 프롬프트 → 마스크 영역 인페인팅
    4. BrushNet composite: hard mask로 마스크 내부만 결과로 교체
    """
    import numpy as np
    from google.genai import types
    from PIL import Image, ImageFilter

    BASE_WARNINGS = [
        "inpainting_used",
        "generation_uses_inpainted_image",
        "not_for_measurement",
    ]

    try:
        client = _get_client()
        prompt = _get_prompt(furniture_type)
        logger.info("Nano Banana inpainting prompt: %s", prompt)

        image = Image.open(image_path).convert("RGB")
        mask = Image.open(mask_path).convert("L")
        w, h = image.size

        # 마스크 강제 이진화
        mask_arr = np.array(mask)
        mask_bin = (mask_arr > 127).astype(np.uint8) * 255
        mask = Image.fromarray(mask_bin, mode="L")

        # Dilation: 객체 경계 + 그림자/잔상 영역까지 포함
        if mask_dilation_px > 0:
            filter_size = max(3, mask_dilation_px * 2 + 1)
            if filter_size % 2 == 0:
                filter_size += 1
            mask = mask.filter(ImageFilter.MaxFilter(size=filter_size))

        # 마스크 영역을 흰색으로 칠한 힌트 이미지 생성
        hint_image = image.copy()
        white = Image.new("RGB", (w, h), (255, 255, 255))
        hint_image.paste(white, mask=mask)

        # Nano Banana API 호출
        response = client.models.generate_content(
            model=_MODEL,
            contents=[prompt, hint_image],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        # 결과 이미지 추출
        result = None
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if part.inline_data:
                    result = Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
                    break
            if result:
                break

        if result is None:
            raise RuntimeError("Nano Banana returned no image")

        # 원본 크기로 복원
        result = result.resize((w, h), Image.LANCZOS)

        # BrushNet 합성: hard mask + 가장자리 미세 블러
        hard_mask_arr = (np.array(mask) > 127).astype(np.uint8) * 255
        hard_mask = Image.fromarray(hard_mask_arr, mode="L")
        composite_mask = hard_mask.filter(ImageFilter.GaussianBlur(radius=1.5))

        composite = image.copy()
        composite.paste(result, mask=composite_mask)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        composite.save(output_path)

        return {
            "status": "done",
            "method": "nano_banana_brushnet_composite",
            "warnings": BASE_WARNINGS,
        }

    except Exception as e:
        logger.error("Nano Banana inpainting failed: %s", e)
        return {
            "status": "failed",
            "method": "nano_banana_unavailable",
            "warnings": ["nano_banana_inpainting_failed_fallback_to_original"],
        }
