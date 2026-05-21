"""Free functions for spritesheet metadata enrichment.

When :func:`assetcache.core.sheet.detect.detect_sheet` returns a
:class:`SheetDetection`, callers can use these helpers to:

* enrich a base :class:`SpriteMeta` with frame/animation fields
* convert ``frameTags`` into a list of :class:`LabelScore` rows

Both the sync :class:`SpritesheetAnalyzer` and the batch :class:`BatchPoller`
share these so the on-disk sheet info translates identically into
search-time data.  Neither helper performs any LLM call — the Gemma
``animation_hint`` augmentation stays inside the sync analyzer (it
requires a composite preview image that the batch path doesn't build).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..sheet.types import AnimationSpec
from ..store import LabelScore, SpriteMeta

if TYPE_CHECKING:
    from ..sheet.detect import SheetDetection


def enrich_sprite_meta_with_sheet(
    base_meta: SpriteMeta,
    detection: "SheetDetection",
) -> SpriteMeta:
    """Copy ``base_meta`` and fill the spritesheet-specific fields.

    Tech fields (width/height/alpha/pixel_art/dominant_colors) come from
    ``base_meta`` untouched; ``frame_w``/``frame_h`` come from the first
    detected frame, and ``animations_json`` is built from
    ``detection.tags`` (JSON sidecar frameTags).  ``animation_tags`` is a
    convenience denormalised list of the dict keys, or ``None`` when no
    tags are present (preserves the legacy column shape).
    """
    if not detection.frames:
        return base_meta

    first = detection.frames[0]
    animations_json: dict = {}
    for tag in detection.tags:
        animations_json[tag.name] = {
            "start_frame": tag.start_frame,
            "end_frame": tag.end_frame,
            "fps_hint": tag.fps_hint,
            "source": tag.source,
        }
    animation_tags = list(animations_json.keys()) if animations_json else None

    return SpriteMeta(
        width=base_meta.width,
        height=base_meta.height,
        has_alpha=base_meta.has_alpha,
        is_pixel_art=base_meta.is_pixel_art,
        dominant_colors=base_meta.dominant_colors,
        frame_w=first.w,
        frame_h=first.h,
        frame_count=len(detection.frames),
        animation_tags=animation_tags,
        animations_json=animations_json or None,
    )


def animations_json_to_specs(
    animations_json: dict | None,
) -> list[AnimationSpec]:
    """``sprite_meta.animations_json`` (dict) → :class:`AnimationSpec` 리스트.

    M11.3 옵션 B — DB 에 저장된 enrich 된 ``sprite_meta`` 의 ``animations_json``
    필드는 ``enrich_sprite_meta_with_sheet`` 가 만든 ``{name: {start_frame,
    end_frame, fps_hint, source}}`` 형태.  이를 다시 :class:`AnimationSpec`
    리스트로 복원해 ``detection_to_animation_labels`` 같은 라벨 합산 helper
    에 그대로 넣을 수 있게 한다.

    누락 필드는 안전 기본값 (start_frame=end_frame=0, fps_hint=12,
    source='cached').  ``animations_json`` 이 ``None`` 이면 빈 리스트 반환.
    """
    if not animations_json:
        return []
    out: list[AnimationSpec] = []
    for name, info in animations_json.items():
        out.append(AnimationSpec(
            name=name,
            start_frame=int(info.get("start_frame", 0)),
            end_frame=int(info.get("end_frame", 0)),
            fps_hint=int(info.get("fps_hint", 12)),
            source=str(info.get("source", "cached")),
        ))
    return out


def detection_to_animation_labels(
    detection: "SheetDetection",
    *,
    source: str = "gemma",
    score: float = 1.0,
) -> list[LabelScore]:
    """Convert ``detection.tags`` to a list of animation-axis :class:`LabelScore`.

    Defaults match the sync analyzer's confidence (score=1.0 for explicit
    JSON tags).  Duplicates by name are collapsed — first occurrence wins.
    ``source`` defaults to ``"gemma"`` to match the existing label rows in
    the DB even though the data didn't come from Gemma.
    """
    out: list[LabelScore] = []
    seen: set[str] = set()
    for tag in detection.tags:
        if tag.name in seen:
            continue
        seen.add(tag.name)
        out.append(LabelScore(
            axis="animation",
            label=tag.name,
            score=score,
            source=source,
            weight="primary",
        ))
    return out
