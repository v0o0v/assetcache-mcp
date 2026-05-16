"""Per-pack aggregate summary written to ``packs.aggregate_meta``.

Captures just enough signal for M3 search and the GUI's "집계" column —
main_style / palette / category distribution / asset count.  The
analysis queue invokes :func:`compute_aggregate` whenever the last
pending row of a pack settles into a terminal state.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .store import Store


def compute_aggregate(store: "Store", pack_id: int) -> dict:
    """Return a small JSON-serialisable summary of the pack."""
    asset_rows = store.assets_for_pack(pack_id)
    asset_count = len(asset_rows)

    # 모든 라벨을 한 쿼리로 모으기
    asset_ids = [a.id for a in asset_rows]
    if not asset_ids:
        return {"asset_count": 0}

    placeholders = ",".join("?" * len(asset_ids))
    label_rows = store.conn.execute(
        f"SELECT axis, label, source FROM asset_labels"
        f" WHERE asset_id IN ({placeholders})",
        asset_ids,
    ).fetchall()

    style_counter: Counter = Counter()
    category_counter: Counter = Counter()
    palette_counter: Counter = Counter()
    for axis, label, _source in label_rows:
        if axis == "style":
            style_counter[label] += 1
        elif axis == "category":
            category_counter[label] += 1
        elif axis == "palette":
            palette_counter[label] += 1

    out: dict = {"asset_count": asset_count}
    if style_counter:
        out["main_style"] = style_counter.most_common(1)[0][0]
    if category_counter:
        total = sum(category_counter.values())
        out["category_dist"] = {
            cat: round(cnt / total, 3)
            for cat, cnt in category_counter.most_common()
        }
    if palette_counter:
        out["palette"] = [p for p, _ in palette_counter.most_common(3)]
    return out


def write_aggregate(store: "Store", pack_id: int) -> dict:
    summary = compute_aggregate(store, pack_id)
    store.update_pack_aggregate(pack_id, json.dumps(summary))
    return summary
