"""Library tab — read-only table of all indexed assets.

M2 surfaces the two new columns the analyzer fills in: ``라벨`` (top-3
labels joined inline) and ``설명`` (Gemma's one-line description in the
call language).
"""

from __future__ import annotations

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


_DEFAULT_LIMIT = 1000


def _tr(text: str) -> str:
    return QCoreApplication.translate("LibraryView", text)


class LibraryView(QWidget):
    """A flat list of all assets — pagination/filtering arrives in M4."""

    def __init__(self, store: "Store", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        headers = (
            _tr("경로"),
            _tr("종류"),
            _tr("파일 크기"),
            _tr("분석 상태"),
            _tr("라벨"),
            _tr("설명"),
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
        rows = self._store.list_assets(limit=_DEFAULT_LIMIT, offset=0)
        # M2: 라벨/설명을 배치 조회로 채운다 (N+1 회피).
        labels_by_asset, description_by_asset = self._collect_extras(rows)

        self.table.setRowCount(len(rows))
        for r, asset in enumerate(rows):
            labels_text = self._top_labels_text(labels_by_asset.get(asset.id, []))
            desc_text = description_by_asset.get(asset.id, "")
            cells = (
                asset.path,
                asset.kind,
                str(asset.file_size),
                asset.analysis_state,
                labels_text,
                desc_text,
            )
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, c, item)

    # -- helpers ------------------------------------------------------

    def _collect_extras(self, rows) -> tuple[dict, dict]:
        if not rows:
            return {}, {}
        ids = [a.id for a in rows]
        placeholders = ",".join("?" * len(ids))

        labels_by_asset: dict[int, list[tuple[str, str, float, str]]] = {}
        for asset_id, axis, label, score, source in self._store.conn.execute(
            f"SELECT asset_id, axis, label, score, source FROM asset_labels"
            f" WHERE asset_id IN ({placeholders})"
            f" ORDER BY asset_id, score DESC",
            ids,
        ).fetchall():
            labels_by_asset.setdefault(int(asset_id), []).append(
                (axis, label, score, source)
            )

        description_by_asset: dict[int, str] = {}
        # Gemma description 은 분석 결과 자체 — assets_fts 의 searchable_text
        # 마지막 토큰들에서 자연어 description 을 발췌하기는 부정확해서
        # 별도 컬럼이 없는 한 빈 문자열로 둔다.  M3 에서 별도 컬럼/뷰 도입.
        # 단, sound_meta.audio_path_used / sprite_meta.dominant_colors 같은
        # 보조 정보가 필요하면 같은 쿼리에 합칠 수 있음.
        return labels_by_asset, description_by_asset

    @staticmethod
    def _top_labels_text(label_rows) -> str:
        # 상위 3개 (axis=label) 만 join — 'source' 가 다른 경우 중복은 한 번만.
        seen: set[tuple[str, str]] = set()
        picks: list[str] = []
        for axis, label, _score, _source in label_rows:
            key = (axis, label)
            if key in seen:
                continue
            seen.add(key)
            picks.append(f"{axis}={label}")
            if len(picks) >= 3:
                break
        return " · ".join(picks)
