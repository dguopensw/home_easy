"""가구 분석 서비스: 가구 종류 추론, 장애물 감지, 생성용 오염물 분석."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from core import _core

logger = logging.getLogger(__name__)


class FurnitureAnalysisService:
    # ── 가구 종류 추론 ─────────────────────────────────────────────────────

    def infer_furniture_type(self, image_path: Path, title: str, description: str) -> dict:
        """판매글 텍스트 + GPT Vision으로 가구 종류를 추론합니다."""
        listing_class = _core.classify_furniture_from_listing(title, description)
        image_class = _core.classify_furniture_from_image(image_path, title, description)
        return _core.reconcile_furniture_type(listing_class, image_class)

    # ── 주요 장애물 분석 ───────────────────────────────────────────────────

    def analyze_major_obstacles(self, image_path: Path, furniture_type: str) -> dict:
        """GPT-4o Vision으로 주요 장애물을 보수적으로 감지합니다."""
        skip = _core._openai_skip_reason()
        if skip:
            return {
                "has_major_obstacle": False,
                "obstacle_summary": "",
                "obstacles": [],
                "reason": f"GPT unavailable: {skip}",
            }

        client = _core.get_openai_client()
        data_url = _core._image_data_url(image_path)

        prompt = (
            f"Analyze this furniture image (type: {furniture_type}) for MAJOR obstacles.\n\n"
            "A MAJOR obstacle significantly covers the furniture's key structural parts "
            "(silhouette, legs, frame, backrest, surface, doors). It would clearly harm "
            "automated background removal or dimension accuracy.\n\n"
            "Examples of MAJOR obstacles: person sitting on/against furniture, "
            "large box/bag/luggage on top, large laptop/monitor on desk, "
            "thick blanket covering most of the piece.\n\n"
            "NOT major obstacles: sofa cushions/pillows included with the piece, "
            "small decorative items, books, remotes, small plants, picture frames "
            "in the background, items that don't hide structural parts.\n\n"
            "Be CONSERVATIVE. Only mark has_major_obstacle=true when truly significant "
            "structural blocking is present. When in doubt → false.\n\n"
            "Return ONLY valid JSON:\n"
            "{\n"
            '  "has_major_obstacle": false,\n'
            '  "obstacle_summary": "",\n'
            '  "obstacles": [\n'
            '    {"name": "laptop", "description": "large laptop on desk surface", '
            '"location": "tabletop center", "importance": "major"}\n'
            "  ],\n"
            '  "reason": "explanation"\n'
            "}"
        )

        try:
            resp = client.chat.completions.create(
                model=_core.VISION_MODEL,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                ]}],
                max_tokens=400,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(resp.choices[0].message.content.strip())
            obstacles = parsed.get("obstacles", [])
            if not isinstance(obstacles, list):
                obstacles = []

            return {
                "has_major_obstacle": bool(parsed.get("has_major_obstacle", False)),
                "obstacle_summary": str(parsed.get("obstacle_summary", "")),
                "obstacles": [
                    {
                        "name": str(o.get("name", "unknown")),
                        "description": str(o.get("description", "")),
                        "location": str(o.get("location", "")),
                        "importance": str(o.get("importance", "major")),
                    }
                    for o in obstacles if isinstance(o, dict)
                ],
                "reason": str(parsed.get("reason", "")),
            }

        except Exception as e:
            _core._mark_openai_unavailable(e)
            logger.warning("Obstacle analysis failed: %s", e)
            return {
                "has_major_obstacle": False,
                "obstacle_summary": "",
                "obstacles": [],
                "reason": f"analysis_failed: {e}",
            }

    # ── 생성용 오염물 분석 ─────────────────────────────────────────────────

    _FAMILY_GUIDANCE: dict[str, str] = {
        "soft_furniture": (
            "\nIMPORTANT — this is soft/upholstered furniture (sofa, lounge chair, armchair, "
            "recliner, or similar). Built-in back cushions, seat cushions, lumbar cushions, "
            "and pillow-like backrests are PART of the furniture structure. "
            "Do NOT mark them as contaminants. "
            "Only flag clearly loose decorative pillows, blankets, or personal items that are "
            "obviously unrelated to the furniture itself. "
            "When in doubt, do NOT flag as contaminant. "
            "Objects that are visually aligned with the backrest or seat cushion and share the "
            "same fabric or material should be treated as part of the furniture, not as contaminants.\n"
        ),
        "bed_type": (
            "\nIMPORTANT — this is a bed or mattress. Pillows, blankets, and bed linen that "
            "are placed ON the mattress are contaminants for 3D generation. "
            "The headboard, bed frame, slats, and legs are PART of the furniture. "
            "Flag loose pillows, duvets, or decorative items on the mattress surface.\n"
        ),
        "rack_or_thin_structure": (
            "\nIMPORTANT — this is a rack, coat stand, or thin shelf structure. "
            "Hanging clothes, bags, or accessories on the rack are contaminants. "
            "The poles, crossbars, base, and brackets are PART of the furniture. "
            "Do NOT flag the structural frame. Only flag items hung or placed on it.\n"
        ),
        "glass_or_reflective": (
            "\nIMPORTANT — this is a glass table or mirror with reflective surfaces. "
            "Items placed ON the glass surface or AROUND the mirror are contaminants. "
            "The glass panel, metal/wooden frame, and legs are PART of the furniture. "
            "Reflections visible through the glass are NOT contaminants.\n"
        ),
        "closed_body": (
            "\nIMPORTANT — this is a closed-body furniture item (bookshelf, cabinet, dresser). "
            "Items stored ON TOP of the furniture or placed IN FRONT of it are contaminants. "
            "Books on shelves that are inside the unit may also be contaminants for 3D generation. "
            "The cabinet body, doors, drawers, and handles are PART of the furniture.\n"
        ),
        "open_leg_hard": (
            "\nFor desk/table: any independent object on the tabletop surface is a contaminant "
            "(laptop, books, cups, lamps, plants, etc.). "
            "For hard chair: items placed ON the seat are contaminants, the chair itself is not.\n"
        ),
    }

    def analyze_generation_contaminants(
        self,
        image_path: Path,
        furniture_type: str,
        masking_family: str = "generic",
    ) -> dict:
        """GPT-4o Vision으로 3D 생성에 영향을 줄 오염물을 감지합니다."""
        skip = _core._openai_skip_reason()
        if skip:
            return {
                "has_generation_contaminants": False,
                "contaminant_summary": "",
                "contaminants": [],
                "reason": f"GPT unavailable: {skip}",
            }

        client = _core.get_openai_client()
        data_url = _core._image_data_url(image_path)
        soft_guidance = self._FAMILY_GUIDANCE.get(masking_family, "")

        prompt = (
            f"Analyze this furniture image (type: {furniture_type}) for objects that would "
            "contaminate 3D model generation.\n\n"
            "These are objects placed ON, AROUND, or CLAMPED to the furniture that are NOT part "
            "of the furniture itself, and would be incorrectly baked into a 3D model if left in.\n\n"
            "Target contaminants: books, laptops, tablets, desk lamps, cups, mugs, bottles, "
            "decorative items, remote controls, small boxes, blankets, clutter, personal items, "
            "monitor arms, monitor stands, monitor mounts, clamp-mounted accessories, "
            "power strips, multi-tap outlets, charging cables, cable clutter, "
            "keyboards, mice, computer peripherals, picture frames, plants.\n\n"
            "Do NOT flag as contaminants:\n"
            "- The furniture structure itself (legs, frame, surface, drawers, backrest)\n"
            f"- Built-in cushions/parts that are included with the {furniture_type}\n"
            "- Built-in handles, knobs, or hardware that are part of the original furniture design\n"
            "- Wall-mounted items behind the furniture (curtains, blinds, window frames)\n\n"
            "For desk/table: any independent object on the tabletop OR clamp-mounted to the desk "
            "is a contaminant, including monitor arms, lamps, power strips, and cables. "
            "A clamp-mounted monitor arm is a user-added accessory, NOT part of the desk design.\n"
            f"{soft_guidance}\n"
            "IMPORTANT: each 'name' field must be a SHORT noun phrase (1-3 words) such as "
            "'monitor arm', 'power strip', 'remote control'. Do NOT include locations or "
            "full sentences in 'name'. Put spatial details in 'location' only.\n"
            "Return ONLY valid JSON:\n"
            "{\n"
            '  "has_generation_contaminants": false,\n'
            '  "contaminant_summary": "",\n'
            '  "contaminants": [\n'
            '    {"name": "tablet", "description": "small black tablet on tabletop", '
            '"location": "rear-left area of tabletop", "removal_priority": "medium"}\n'
            "  ],\n"
            '  "reason": "explanation"\n'
            "}"
        )

        try:
            resp = client.chat.completions.create(
                model=_core.VISION_MODEL,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                ]}],
                max_tokens=500,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(resp.choices[0].message.content.strip())
            contaminants = parsed.get("contaminants", [])
            if not isinstance(contaminants, list):
                contaminants = []

            return {
                "has_generation_contaminants": bool(parsed.get("has_generation_contaminants", False)),
                "contaminant_summary": str(parsed.get("contaminant_summary", "")),
                "contaminants": [
                    {
                        "name": str(c.get("name", "unknown")),
                        "description": str(c.get("description", "")),
                        "location": str(c.get("location", "")),
                        "removal_priority": str(c.get("removal_priority", "medium")),
                    }
                    for c in contaminants if isinstance(c, dict)
                ],
                "reason": str(parsed.get("reason", "")),
            }

        except Exception as e:
            _core._mark_openai_unavailable(e)
            logger.warning("Generation contaminant analysis failed: %s", e)
            return {
                "has_generation_contaminants": False,
                "contaminant_summary": "",
                "contaminants": [],
                "reason": f"analysis_failed: {e}",
            }
