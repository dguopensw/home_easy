"""Nano Banana end-to-end 위탁 — 시도 2(Banana 단독) 재현용.

이 모듈은 마스크 없이 **원본 이미지 전체**와 "가구만 남기고 모든 장애물/배경을
제거하라"는 지시 프롬프트를 Nano Banana(Gemini 3 Pro Image)에 보내, 전처리 전
과정을 단일 모델 호출로 위탁한다.

Nano Banana는 입력 이미지를 '참고'하여 완전히 새로운 이미지를 생성하므로,
결과적으로 가구의 종횡비·다리 위치·시트 곡률 등 세부 구조가 미세하게 변형된다.
BrushNet 합성(부분 인페인팅)과 달리 가구 본체 픽셀이 보존되지 않으며, 이는
보고서 '시도 2'의 '가구 비율 변형' 한계를 발표 자료용 이미지로 시연하기 위한
의도된 동작이다.
"""
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
        logger.info("Gemini (Nano Banana E2E) client initialized.")
    return _client


_MODEL = os.environ.get("NANO_BANANA_MODEL", "gemini-3-pro-image-preview")

_E2E_PROMPT_TEMPLATE = (
    "Edit this photo so that ONLY the main {furniture} remains. "
    "Remove every other object, clutter, person, hand, decoration, and the entire "
    "background, and replace the background with a clean, plain light-gray studio backdrop. "
    "Produce a single photorealistic product photo of the {furniture}, well lit and centered. "
    "Keep the {furniture} fully visible and uncropped."
)


def _build_prompt(furniture_type: str) -> str:
    furniture = (furniture_type or "furniture piece").strip() or "furniture piece"
    return _E2E_PROMPT_TEMPLATE.format(furniture=furniture)


def inpaint_with_banana_e2e(
    image_path: Path,
    output_path: Path,
    furniture_type: str = "",
) -> dict:
    """원본 이미지 전체를 Nano Banana에 위탁해 재생성한다 (시도 2 재현).

    마스크/합성 없음 — 모델이 이미지 전체를 재창작하므로 가구 비율이 변형된다.

    Returns:
        status/method/warnings/diagnostics 딕셔너리. diagnostics에는 원본 대비
        출력 종횡비·stretch 비율이 포함되어 '비율 변형' 정량 비교에 쓸 수 있다.
    """
    from google.genai import types
    from PIL import Image

    BASE_WARNINGS = [
        "end_to_end_generation_used",
        "furniture_proportions_may_be_altered",
        "not_for_measurement",
        "furniture_body_pixels_not_preserved",
    ]

    try:
        client = _get_client()
        prompt = _build_prompt(furniture_type)
        logger.info("Nano Banana E2E prompt: %s", prompt)

        image = Image.open(image_path).convert("RGB")
        w, h = image.size

        # 원본 이미지 전체 + 지시 프롬프트 → 단일 호출 위탁
        response = client.models.generate_content(
            model=_MODEL,
            contents=[prompt, image],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                seed=42,
                temperature=0.2,
            ),
        )

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

        banana_w, banana_h = result.size
        orig_aspect = w / h
        banana_aspect = banana_w / banana_h
        stretch_x = w / banana_w
        stretch_y = h / banana_h
        aspect_drift = abs(banana_aspect - orig_aspect) / orig_aspect
        logger.info(
            "Banana E2E result: %dx%d (aspect %.3f) vs original %dx%d (aspect %.3f) | "
            "aspect_drift=%.3f",
            banana_w, banana_h, banana_aspect, w, h, orig_aspect, aspect_drift,
        )

        # 결과를 원본 해상도로 맞춰 저장 (시각 비교 편의 — 이 resize 자체도 변형 요인)
        result_resized = result.resize((w, h), Image.LANCZOS)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        result_resized.save(output_path)

        # 원본 해상도로 강제 resize하지 않은 native 결과도 함께 보존(비율 비교용)
        native_path = output_path.parent / (output_path.stem + "_native" + output_path.suffix)
        result.save(native_path)

        return {
            "status": "done",
            "method": "nano_banana_end_to_end",
            "warnings": BASE_WARNINGS,
            "diagnostics": {
                "original_size": [w, h],
                "banana_output_size": [banana_w, banana_h],
                "original_aspect": round(orig_aspect, 3),
                "banana_aspect": round(banana_aspect, 3),
                "stretch_x": round(stretch_x, 3),
                "stretch_y": round(stretch_y, 3),
                "aspect_drift": round(aspect_drift, 3),
                "native_output_file": native_path.name,
            },
        }

    except Exception as e:
        logger.error("Nano Banana E2E failed: %s", e)
        return {
            "status": "failed",
            "method": "nano_banana_e2e_unavailable",
            "warnings": ["nano_banana_e2e_failed"],
            "error": str(e),
        }
