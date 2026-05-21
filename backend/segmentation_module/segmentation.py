"""SAM3-based segmentation module.

Wraps SAM3 (facebook/sam3) to expose the interface expected by app.py:
  from segmentation import create_segmenter
  segmenter = create_segmenter(device="cuda", prefer="grounded_sam")

The returned segmenter exposes:
  - segmenter.processor  : callable + post_process_grounded_object_detection()
  - segmenter.detector   : callable (no-op; processor handles detection)
  - segmenter.predictor  : set_image() + predict()
  - segmenter.device     : device string
  - segmenter.segment()  : single-shot fallback
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
    "left", "right", "top", "bottom", "front", "back", "side", "middle",
    "upper", "lower", "corner", "center", "near", "on", "in", "at", "of",
    "inside", "outside", "above", "below", "behind",
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
# Proxy: wraps Sam3Processor to look like a HF GroundingDINO processor
# ---------------------------------------------------------------------------

class _ProcessorProxy:
    """Adapts Sam3Processor to the HF-style API used in app.py.

    app.py call sequence:
      inputs = gsam.processor(images=img, text=prompt, return_tensors="pt")
      inputs = {k: v.to(device) for k, v in inputs.items()}   # move to device
      outputs = gsam.detector(**inputs)
      results = gsam.processor.post_process_grounded_object_detection(outputs, ...)
    """

    def __init__(self, sam3_processor):
        self._p = sam3_processor
        self._last_state: dict | None = None

    def __call__(self, images, text: str, return_tensors: str = "pt") -> dict:
        # Split GroundingDINO-style compound prompt ("obj1. obj2. obj3.")
        # and query SAM3 separately per concept, then merge detections.
        concepts = [c.strip().rstrip(".") for c in text.split(".") if c.strip()]
        if not concepts:
            concepts = [text]

        all_boxes, all_scores, all_masks = [], [], []

        ctx = (torch.autocast("cuda", dtype=torch.bfloat16)
               if torch.cuda.is_available() else contextlib.nullcontext())

        with ctx:
            for concept in concepts:
                # Strip trailing location words — keep only the noun phrase
                # e.g. "books left side middle shelf" → "books"
                noun = _extract_noun(concept)
                state = self._p.set_image(images)
                state = self._p.set_text_prompt(prompt=noun, state=state)
                if "boxes" in state and len(state["boxes"]) > 0:
                    all_boxes.append(state["boxes"])
                    all_scores.append(state["scores"])
                    if "masks" in state and len(state["masks"]) > 0:
                        all_masks.append(state["masks"])

        if all_boxes:
            merged = {
                "boxes": torch.cat(all_boxes, dim=0),
                "scores": torch.cat(all_scores, dim=0),
            }
            if all_masks:
                merged["masks"] = torch.cat(all_masks, dim=0)
            self._last_state = merged
        else:
            self._last_state = {}

        return {"_dummy": torch.zeros(1)}

    def post_process_grounded_object_detection(
        self,
        outputs,
        input_ids=None,
        threshold: float = 0.15,
        text_threshold: float = 0.15,
        target_sizes=None,
    ) -> list[dict]:
        state = self._last_state
        if state is None or "boxes" not in state or len(state["boxes"]) == 0:
            return [{"boxes": torch.zeros(0, 4), "labels": [], "scores": torch.zeros(0)}]

        boxes = state["boxes"].cpu().float()    # (N, 4) XYXY pixel coords
        scores = state["scores"].cpu().float()  # (N,)

        keep = scores > threshold
        boxes = boxes[keep]
        scores = scores[keep]
        labels = ["furniture"] * int(keep.sum())
        return [{"boxes": boxes, "labels": labels, "scores": scores}]


# ---------------------------------------------------------------------------
# Proxy: wraps Sam3Processor to look like a SAM v1 SamPredictor
# ---------------------------------------------------------------------------

class _PredictorProxy:
    """Adapts Sam3Processor to the SAM v1 predictor API used in app.py.

    app.py call sequence:
      gsam.predictor.set_image(image_np)
      masks, scores, _ = gsam.predictor.predict(box=box, multimask_output=True)
    """

    def __init__(self, sam3_processor):
        self._p = sam3_processor
        self._pil_image: Image.Image | None = None
        self._size: tuple[int, int] | None = None  # (W, H)

    def set_image(self, image_np: np.ndarray) -> None:
        self._pil_image = Image.fromarray(image_np.astype(np.uint8))
        self._size = (image_np.shape[1], image_np.shape[0])

    def predict(
        self, box: torch.Tensor | np.ndarray, multimask_output: bool = True
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """box: [x1, y1, x2, y2] pixel coords."""
        if self._pil_image is None:
            raise RuntimeError("Call set_image() before predict()")

        W, H = self._size
        x1, y1, x2, y2 = (float(v) for v in box[:4])

        # Convert xyxy → normalized cxcywh expected by SAM3
        cx = (x1 + x2) / 2.0 / W
        cy = (y1 + y2) / 2.0 / H
        bw = (x2 - x1) / W
        bh = (y2 - y1) / H
        norm_box_cxcywh = [cx, cy, bw, bh]

        with (torch.autocast("cuda", dtype=torch.bfloat16) if torch.cuda.is_available() else contextlib.nullcontext()):
            state = self._p.set_image(self._pil_image)
            state = self._p.add_geometric_prompt(state=state, box=norm_box_cxcywh, label=True)

        if "masks" not in state or len(state["masks"]) == 0:
            empty = np.zeros((1, H, W), dtype=bool)
            return empty, np.array([0.0]), np.zeros((1, H, W))

        masks_t = state["masks"].cpu().float()   # (N, 1, H, W)
        scores_t = state["scores"].cpu().float() # (N,)

        masks_np = masks_t.squeeze(1).numpy().astype(bool)   # (N, H, W)
        scores_np = scores_t.numpy()
        return masks_np, scores_np, masks_np.astype(float)


# ---------------------------------------------------------------------------
# Detector proxy — no-op; processor already ran the model
# ---------------------------------------------------------------------------

class _DetectorProxy:
    def __call__(self, **inputs):
        return inputs


# ---------------------------------------------------------------------------
# Main segmenter class
# ---------------------------------------------------------------------------

class Sam3Segmenter:
    """Segmenter backed by SAM3, exposing the interface app.py expects."""

    def __init__(self, model, sam3_processor, device: str):
        self._model = model
        self._sam3_processor = sam3_processor
        self.device = device

        self.processor = _ProcessorProxy(sam3_processor)
        self.predictor = _PredictorProxy(sam3_processor)
        self.detector = _DetectorProxy()

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
