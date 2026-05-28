"""SAM3-based segmentation module.

Direct SAM3 wrapper — call sites use:
  from segmentation import create_segmenter
  segmenter = create_segmenter(device="cuda")

The returned Sam3Segmenter exposes:
  - segmenter.segment_text(image, prompts, threshold)  : text → boxes/masks
  - segmenter.segment_box(image, box)                  : box  → masks
  - segmenter.segment(image_path, furniture_type)      : single-shot fallback
  - segmenter.device                                   : device string
"""

from __future__ import annotations

import contextlib
import os
import sys

import numpy as np
import torch
from PIL import Image


# Location/direction words that follow the noun phrase in GPT-generated prompts.
_LOCATION_WORDS = {
    "left", "right", "top", "bottom", "front", "back", "rear", "side", "middle",
    "upper", "lower", "corner", "center", "central", "centered",
    "leftmost", "rightmost", "topmost", "bottommost", "mid",
    "near", "on", "in", "at", "of",
    "inside", "outside", "above", "below", "behind",
    "area", "region", "section",
}


def _extract_noun(phrase: str) -> str:
    """Return only the noun part of a location-qualified phrase.

    e.g. "books left side middle shelf" → "books"
         "vase with flowers right side" → "vase with flowers"
         "cup"                          → "cup"
    """
    words = phrase.split()
    noun_words = []
    for w in words:
        if w.lower() in _LOCATION_WORDS:
            break
        noun_words.append(w)
    return " ".join(noun_words) if noun_words else phrase


# ---------------------------------------------------------------------------
# Result type used by the fallback .segment() path
# ---------------------------------------------------------------------------

class SegmentResult:
    def __init__(self, mask: np.ndarray, label: str = "furniture", confidence: float = 0.0):
        self.mask = mask
        self.label = label
        self.confidence = confidence


# ---------------------------------------------------------------------------
# Main segmenter class
# ---------------------------------------------------------------------------

class Sam3Segmenter:
    """Segmenter backed by SAM3, exposing the interface app.py expects."""

    def __init__(self, model, sam3_processor, device: str):
        self._model = model
        self._sam3_processor = sam3_processor
        self.device = device

        # 직접 호출 경로용 디버그 상태
        self._last_sam3_prompts: list[str] = []

    # ── 직접 호출 인터페이스 ────────────────────────────────────────────────

    def segment_text(
        self,
        image,
        prompts: list[str],
        threshold: float = 0.20,
    ) -> dict:
        """텍스트 프롬프트 리스트로 객체 마스크 생성 (SAM3 직접 호출).

        각 prompt 에 대해 SAM3 의 set_text_prompt 호출 → 박스/스코어/마스크 모음을 union.
        proxy 와 동일한 _extract_noun 전처리를 거치므로 caller 가 GPT-스타일 phrase 를
        그대로 넘겨도 됨.

        Args:
            image: PIL.Image 또는 numpy.ndarray (RGB).
            prompts: 짧은 명사구 리스트.
            threshold: confidence score 컷오프 (proxy 의 post_process 기본과 동일).

        Returns:
            {
              "boxes": tensor (M, 4) xyxy pixel coords (threshold 통과 박스만),
              "scores": tensor (M,),
              "masks": tensor (M, 1, H, W) 또는 None,
              "sam3_actual_prompts": list[str]  # _extract_noun 후 SAM3 가 실제로 받은 phrase
            }
        """
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image.astype(np.uint8))

        all_boxes, all_scores, all_masks = [], [], []
        actual_prompts: list[str] = []

        ctx = (torch.autocast("cuda", dtype=torch.bfloat16)
               if torch.cuda.is_available() else contextlib.nullcontext())

        with ctx:
            for raw in prompts:
                noun = _extract_noun(raw.strip().rstrip("."))
                if not noun:
                    continue
                actual_prompts.append(noun)
                state = self._sam3_processor.set_image(image)
                state = self._sam3_processor.set_text_prompt(prompt=noun, state=state)
                if "boxes" in state and len(state["boxes"]) > 0:
                    all_boxes.append(state["boxes"])
                    all_scores.append(state["scores"])
                    if "masks" in state and len(state["masks"]) > 0:
                        all_masks.append(state["masks"])

        self._last_sam3_prompts = actual_prompts

        if not all_boxes:
            return {
                "boxes": torch.zeros(0, 4),
                "scores": torch.zeros(0),
                "masks": None,
                "sam3_actual_prompts": actual_prompts,
            }

        boxes = torch.cat(all_boxes, dim=0).cpu().float()
        scores = torch.cat(all_scores, dim=0).cpu().float()
        masks = torch.cat(all_masks, dim=0) if all_masks else None

        keep = scores > threshold
        return {
            "boxes": boxes[keep],
            "scores": scores[keep],
            "masks": masks[keep] if masks is not None else None,
            "sam3_actual_prompts": actual_prompts,
        }

    def segment_box(
        self,
        image,
        box,
    ) -> tuple[np.ndarray, np.ndarray]:
        """단일 박스로 SAM3 마스크 생성 (proxy.predictor.predict 와 동일 동작).

        Args:
            image: PIL.Image 또는 numpy.ndarray (RGB).
            box: [x1, y1, x2, y2] pixel xyxy.

        Returns:
            (masks_np, scores_np) — (N, H, W) bool, (N,) float.
        """
        if isinstance(image, np.ndarray):
            pil_image = Image.fromarray(image.astype(np.uint8))
        else:
            pil_image = image
        W, H = pil_image.size

        x1, y1, x2, y2 = (float(v) for v in box[:4])
        cx = (x1 + x2) / 2.0 / W
        cy = (y1 + y2) / 2.0 / H
        bw = (x2 - x1) / W
        bh = (y2 - y1) / H
        norm_box = [cx, cy, bw, bh]

        ctx = (torch.autocast("cuda", dtype=torch.bfloat16)
               if torch.cuda.is_available() else contextlib.nullcontext())
        with ctx:
            state = self._sam3_processor.set_image(pil_image)
            state = self._sam3_processor.add_geometric_prompt(
                state=state, box=norm_box, label=True,
            )

        if "masks" not in state or len(state["masks"]) == 0:
            empty = np.zeros((1, H, W), dtype=bool)
            return empty, np.array([0.0])

        masks_t = state["masks"].cpu().float()
        scores_t = state["scores"].cpu().float()
        masks_np = masks_t.squeeze(1).numpy().astype(bool)
        scores_np = scores_t.numpy()
        return masks_np, scores_np

    # ── 레거시 segment() (단일 fallback path) ──────────────────────────────

    def segment(
        self,
        image_path,
        furniture_type: str | None = None,
        auto_detect: bool = True,
    ) -> SegmentResult:
        """Single-shot text-based segmentation (fallback path)."""
        image = Image.open(image_path).convert("RGB")
        W, H = image.size

        prompt = furniture_type if furniture_type else "furniture"
        with (torch.autocast("cuda", dtype=torch.bfloat16) if torch.cuda.is_available() else contextlib.nullcontext()):
            state = self._sam3_processor.set_image(image)
            state = self._sam3_processor.set_text_prompt(prompt=prompt, state=state)

        if "masks" not in state or len(state["masks"]) == 0:
            return SegmentResult(
                mask=np.zeros((H, W), dtype=np.uint8),
                label=prompt,
                confidence=0.0,
            )

        masks = state["masks"].cpu().float()   # (N, 1, H, W)
        scores = state["scores"].cpu().float()

        best_idx = int(scores.argmax())
        mask_np = masks[best_idx, 0].numpy().astype(np.uint8) * 255

        return SegmentResult(
            mask=mask_np,
            label=prompt,
            confidence=float(scores[best_idx]),
        )


# ---------------------------------------------------------------------------
# Public factory function
# ---------------------------------------------------------------------------

def create_segmenter(device: str = "cuda", prefer: str = "grounded_sam") -> Sam3Segmenter:
    """Load SAM3 and return a segmenter compatible with app.py."""
    import torch
    import sam3 as _sam3_pkg
    from sam3 import build_sam3_image_model
    from sam3.model.sam3_image_processor import Sam3Processor

    # Always use CUDA when available — app.py defaults to "cpu" but SAM3 needs GPU
    if torch.cuda.is_available():
        device = "cuda"

    bpe_path = os.path.join(
        os.path.dirname(_sam3_pkg.__file__), "assets", "bpe_simple_vocab_16e6.txt.gz"
    )

    model = build_sam3_image_model(
        bpe_path=bpe_path,
        device=device,
        load_from_HF=True,
    )

    sam3_processor = Sam3Processor(model)
    return Sam3Segmenter(model, sam3_processor, device)
