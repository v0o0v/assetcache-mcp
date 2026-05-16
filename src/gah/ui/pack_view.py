"""Pack tab — read-only table of registered packs.

M2 adds the ``집계`` column populated from ``packs.aggregate_meta``
(written by the analysis queue once a pack's last asset settles).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:  # pragma: no cover
    from ..core.store import Store


def _tr(text: str) -> str:
    return QCoreApplication.translate("PackView", text)


class PackView(QWidget):
    """A simple QTableWidget bound to ``store.list_packs()``."""

    def __init__(self, store: "Store", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        headers = (
            _tr("이름"),
            _tr("표시명"),
            _tr("벤더"),
            _tr("라이선스"),
            _tr("에셋 수"),
            _tr("활성"),
            _tr("집계"),
            _tr("최근 스캔"),
        )
        self.table = QTableWidget(0, len(headers), self)
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)

        layout.addWidget(self.table)

    def refresh(self) -> None:
        packs = self._store.list_packs(include_disabled=True)
        self.table.setRowCount(len(packs))
        for row, pack in enumerate(packs):
            asset_count = self._store.count_assets_in_pack(pack.id)
            aggregate_text = self._aggregate_summary(pack.id)
            cells = (
                pack.name,
                pack.display_name or "",
                pack.vendor or "",
                pack.license or "",
                str(asset_count),
                "✓" if pack.enabled else "—",
                aggregate_text,
                str(pack.scanned_at) if pack.scanned_at is not None else "",
            )
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, col, item)

    # -- helpers ------------------------------------------------------

    def _aggregate_summary(self, pack_id: int) -> str:
        row = self._store.conn.execute(
            "SELECT aggregate_meta FROM packs WHERE id = ?", (pack_id,)
        ).fetchone()
        if not row or not row[0]:
            return _tr("(분석 중)")
        try:
            data = json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return ""
        bits: list[str] = []
        if "main_style" in data:
            bits.append(str(data["main_style"]))
        cat_dist = data.get("category_dist") or {}
        if cat_dist:
            top_two = list(cat_dist.items())[:2]
            bits.append(", ".join(f"{c}({v})" for c, v in top_two))
        return " · ".join(bits)
