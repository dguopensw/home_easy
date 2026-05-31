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
    "sofa": (
        "Show only the smooth, continuous sofa upholstery fabric across this blank area, "
        "matching the visible sofa body's texture, color, and lighting. "
        "The masked area should look like a flat unobstructed section of the sofa body itself. "
        "Do NOT draw cushions, pillows, blankets, decorations, or any objects."
    ),
    "chair": (
        "Show only the smooth, continuous chair upholstery fabric across this blank area, "
        "matching the visible chair body's texture, color, and lighting. "
        "Do NOT draw cushions, pillows, decorations, or any objects."
    ),
    "desk": (
        "Show only the smooth, continuous desk top across this blank area, "
        "matching the visible desk's wood or material texture, color, and lighting. "
        "Do NOT draw items, papers, devices, decorations, or any objects."
    ),
    "table": (
        "Show only the smooth, continuous table top across this blank area, "
        "matching the visible table material, color, and lighting. "
        "Do NOT draw items, decorations, or any objects."
    ),
    "bed": (
        "Show only the smooth, flat bed sheet surface across this blank area, "
        "matching the visible sheet's texture, color, and lighting. "
        "Do NOT draw pillows, blankets, folds, or any objects."
    ),
    "wardrobe": (
        "Show only the floor or wall behind the wardrobe across this blank area, "
        "matching the visible texture, color, and lighting. "
        "Do NOT draw any objects."
    ),
    "drawer": (
        "Show only the smooth drawer front panel across this blank area, "
        "matching the visible material texture, color, and lighting. "
        "Do NOT draw handles, items, or any objects."
    ),
    "shelf": (
        "Show only the empty shelf panel surface across this blank area, "
        "matching the visible shelf material, color, and lighting. "
        "Do NOT draw books, items, decorations, or any objects."
    ),
}

_DEFAULT_PROMPT = (
    "Show only the smooth, continuous furniture body surface across this blank area, "
    "matching the surrounding texture, color, and lighting. "
    "Do NOT draw any objects."
)

_MODEL = os.environ.get("NANO_BANANA_MODEL", "gemini-3-pro-image-preview")


def _get_prompt(furniture_type: str) -> str:
    return _FURNITURE_PROMPTS.get(furniture_type.lower(), _DEFAULT_PROMPT)


def inpaint_with_banana(
    image_path: Path,
    mask_path: Path,
    output_path: Path,
    furniture_type: str = "",
    mask_dilation_px: int = 15,
    composite_blur_radius: float = 1.5,
    composite_mode: str = "blur",
    composite_dilate_px: int = 10,
) -> dict:
    """Nano Banana 인페인팅 후 BrushNet 스타일로 원본에 합성합니다.

    composite_mode: 합성 방식.
        - "blur"(기본): hard mask + GaussianBlur(composite_blur_radius) 페더 페이스트
        - "seamless": Poisson seamless clone(NORMAL) — 패치 톤을 주변에 맞춰 경계 흡수
        - "seamless_mixed": Poisson seamless clone(MIXED) — 강한 원본 그라데이션 보존
    composite_blur_radius: blur 모드의 경계 GaussianBlur 반경(px). 0 이하이면
        블러 없이 하드 페이스트. 운영 기본값은 1.5.
    composite_dilate_px: 합성 영역을 원본 마스크 대비 N px 확장(운영 기본 10).
        장애물 그림자/잔흔까지 banana 결과로 덮어 자국·SAM3 구멍을 줄인다.
        mask_dilation_px 로 상한. 가구 마스크/치수에는 영향 없음(생성용 이미지 픽셀만 변경).

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

        # 마스크 강제 이진화 — 원본 (BrushNet 합성용, 가구 본체 침범 방지)
        mask_arr = np.array(mask)
        mask_bin = (mask_arr > 127).astype(np.uint8) * 255
        original_mask = Image.fromarray(mask_bin, mode="L")

        # Dilation: 그림자/경계까지 자연스러운 인페인팅을 위해 확장 (Banana 입력용)
        mask = original_mask
        if mask_dilation_px > 0:
            filter_size = max(3, mask_dilation_px * 2 + 1)
            if filter_size % 2 == 0:
                filter_size += 1
            mask = mask.filter(ImageFilter.MaxFilter(size=filter_size))

        # 마스크 영역을 흰색으로 칠한 힌트 이미지 생성
        hint_image = image.copy()
        white = Image.new("RGB", (w, h), (255, 255, 255))
        hint_image.paste(white, mask=mask)

        # Nano Banana API 호출 (seed + low temperature 로 deterministic 화)
        response = client.models.generate_content(
            model=_MODEL,
            contents=[prompt, hint_image],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                seed=42,
                temperature=0.2,
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

        # 진단 로그: Banana 출력 크기 vs 원본 크기 비교 (stretch 진단용)
        banana_w, banana_h = result.size
        orig_aspect = w / h
        banana_aspect = banana_w / banana_h
        stretch_x = w / banana_w
        stretch_y = h / banana_h
        logger.info(
            "Banana result: %dx%d (aspect %.3f) → resize to original %dx%d (aspect %.3f) | "
            "stretch_x=%.3f stretch_y=%.3f",
            banana_w, banana_h, banana_aspect, w, h, orig_aspect, stretch_x, stretch_y,
        )

        # 원본 크기로 복원
        result = result.resize((w, h), Image.LANCZOS)

        # BrushNet 합성: dilation 안 된 원본 마스크 사용 (가구 본체 영역 100% 보존)
        hard_mask_arr = (np.array(original_mask) > 127).astype(np.uint8) * 255

        # 합성 영역 확장 — 장애물 그림자/잔흔까지 banana 결과로 덮음.
        # banana는 +mask_dilation_px 까지 이미 그렸으므로 그 범위 내에서만 확장.
        eff_dilate = max(0, min(composite_dilate_px, mask_dilation_px))
        if eff_dilate > 0:
            fs = eff_dilate * 2 + 1
            dilated = Image.fromarray(hard_mask_arr, mode="L").filter(ImageFilter.MaxFilter(size=fs))
            paste_mask_arr = (np.array(dilated) > 127).astype(np.uint8) * 255
        else:
            paste_mask_arr = hard_mask_arr

        mode = (composite_mode or "blur").strip().lower()

        def _feather_paste() -> "Image.Image":
            hard_mask = Image.fromarray(paste_mask_arr, mode="L")
            if composite_blur_radius and composite_blur_radius > 0:
                cmask = hard_mask.filter(ImageFilter.GaussianBlur(radius=composite_blur_radius))
            else:
                cmask = hard_mask  # 블러 없는 하드 페이스트
            out = image.copy()
            out.paste(result, mask=cmask)
            return out

        if mode in ("seamless", "seamless_mixed"):
            import cv2

            ys, xs = np.where(paste_mask_arr > 0)
            if len(xs) == 0:
                composite = image.copy()
            else:
                # seamlessClone은 마스크가 이미지 경계에 닿으면 실패 → 테두리 1px 제거
                safe = paste_mask_arr.copy()
                safe[0, :] = 0; safe[-1, :] = 0; safe[:, 0] = 0; safe[:, -1] = 0
                sy, sx = np.where(safe > 0)
                if len(sx) == 0:
                    safe, sy, sx = paste_mask_arr, ys, xs
                center = (int((sx.min() + sx.max()) // 2), int((sy.min() + sy.max()) // 2))
                src = cv2.cvtColor(np.array(result), cv2.COLOR_RGB2BGR)
                dst = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                flag = cv2.NORMAL_CLONE if mode == "seamless" else cv2.MIXED_CLONE
                try:
                    blended = cv2.seamlessClone(src, dst, safe, center, flag)
                    composite = Image.fromarray(cv2.cvtColor(blended, cv2.COLOR_BGR2RGB))
                except Exception as ce:
                    logger.warning("seamlessClone failed (%s) → feather fallback", ce)
                    composite = _feather_paste()
        else:
            composite = _feather_paste()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        composite.save(output_path)

        return {
            "status": "done",
            "method": "nano_banana_brushnet_composite",
            "warnings": BASE_WARNINGS,
            "diagnostics": {
                "original_size": [w, h],
                "banana_output_size": [banana_w, banana_h],
                "original_aspect": round(orig_aspect, 3),
                "banana_aspect": round(banana_aspect, 3),
                "stretch_x": round(stretch_x, 3),
                "stretch_y": round(stretch_y, 3),
                "composite_blur_radius": composite_blur_radius,
                "composite_mode": mode,
                "composite_dilate_px": eff_dilate,
            },
        }

    except Exception as e:
        logger.error("Nano Banana inpainting failed: %s", e)
        return {
            "status": "failed",
            "method": "nano_banana_unavailable",
            "warnings": ["nano_banana_inpainting_failed_fallback_to_original"],
        }
