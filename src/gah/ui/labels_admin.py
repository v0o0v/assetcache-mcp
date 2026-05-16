"""Labels admin dialog.

Lets the user inspect, extend, and edit the 24-axis label vocabulary
that drives the analyzer / CLIP labeler / future M3 search.  All
mutations flow through :class:`gah.core.labels.LabelRegistry` so the
in-memory cache is invalidated and the next analysis sees the new
state immediately.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.labels import LabelValidationError

if TYPE_CHECKING:  # pragma: no cover
    from ..core.labels import LabelRegistry


def _tr(text: str) -> str:
    return QCoreApplication.translate("LabelsAdminDialog", text)


_COL_LABEL, _COL_STATE, _COL_SOURCE, _COL_DESC = 0, 1, 2, 3


class LabelsAdminDialog(QDialog):
    """A simple QDialog that mirrors the ``labels`` table."""

    def __init__(
        self,
        registry: "LabelRegistry",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(_tr("라벨 관리"))
        self.resize(720, 520)
        self.registry = registry

        layout = QVBoxLayout(self)

        # ── 축 선택 ──────────────────────────────────────────────
        axis_row = QHBoxLayout()
        axis_row.addWidget(QLabel(_tr("축")))
        self.axis_combo = QComboBox(self)
        for axis in registry.list_axes():
            self.axis_combo.addItem(axis)
        self.axis_combo.currentTextChanged.connect(self._on_axis_changed)
        axis_row.addWidget(self.axis_combo, 1)
        layout.addLayout(axis_row)

        # ── 라벨 테이블 ─────────────────────────────────────────
        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels((
            _tr("라벨"), _tr("상태"), _tr("출처"), _tr("설명"),
        ))
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.itemChanged.connect(self._on_table_item_changed)
        layout.addWidget(self.table, 1)

        # ── 추가 입력 + 버튼 ────────────────────────────────────
        add_row = QHBoxLayout()
        self.add_label_input = QLineEdit(self)
        self.add_label_input.setPlaceholderText(
            _tr("새 라벨 토큰 (영문 소문자/숫자/_)")
        )
        self.add_button = QPushButton(_tr("추가"), self)
        self.add_button.clicked.connect(self._on_add_clicked)
        self.toggle_button = QPushButton(_tr("선택 토글"), self)
        self.toggle_button.clicked.connect(self._on_toggle_clicked)
        add_row.addWidget(self.add_label_input, 1)
        add_row.addWidget(self.add_button)
        add_row.addWidget(self.toggle_button)
        layout.addLayout(add_row)

        # ── 인라인 에러 + 안내 ──────────────────────────────────
        self.error_label = QLabel("", self)
        self.error_label.setStyleSheet("color: #c0392b;")
        layout.addWidget(self.error_label)

        layout.addWidget(QLabel(_tr(
            "비활성화한 라벨은 다음 분석부터 사용되지 않습니다."
            " 기존 라벨 데이터는 보존됩니다."
        )))

        # 첫 번째 축으로 진입
        if self.axis_combo.count() > 0:
            self.select_axis(self.axis_combo.itemText(0))

    # -- public helpers (also used by the test suite) ---------------

    def select_axis(self, axis: str) -> None:
        # 콤보박스 동기화
        idx = self.axis_combo.findText(axis)
        if idx >= 0 and self.axis_combo.currentIndex() != idx:
            self.axis_combo.setCurrentIndex(idx)
        self._refresh_table(axis)

    def toggle_enabled_for(self, label: str, enabled: bool) -> None:
        self.registry.set_enabled(self.current_axis(), label, enabled)
        self._refresh_table(self.current_axis())

    def edit_description_for(self, label: str, description: str) -> None:
        self.registry.set_description(self.current_axis(), label, description)
        self._refresh_table(self.current_axis())

    def row_has_warning(self, label: str) -> bool:
        for r in range(self.table.rowCount()):
            cell = self.table.item(r, _COL_LABEL)
            if cell is None:
                continue
            text = cell.text()
            # 경고 prefix 가 붙어 있어도 같은 라벨로 인식
            if text.lstrip("⚠ ").strip() == label:
                return "⚠" in text
        return False

    def current_axis(self) -> str:
        return self.axis_combo.currentText()

    # -- internals ---------------------------------------------------

    def _on_axis_changed(self, axis: str) -> None:
        self._refresh_table(axis)

    def _refresh_table(self, axis: str) -> None:
        rows = self.registry.list_labels(
            axis=axis, enabled_only=False, with_description=True
        )
        # itemChanged 가 refresh 도중 발화하지 않게 일시 해제
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            warning_prefix = ""
            if row.source == "user" and not (row.description or "").strip():
                warning_prefix = "⚠ "
            label_item = QTableWidgetItem(f"{warning_prefix}{row.label}")
            label_item.setFlags(label_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, _COL_LABEL, label_item)

            state_item = QTableWidgetItem(
                _tr("활성") if row.enabled else _tr("비활성")
            )
            state_item.setFlags(state_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, _COL_STATE, state_item)

            src_item = QTableWidgetItem(row.source)
            src_item.setFlags(src_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, _COL_SOURCE, src_item)

            desc_item = QTableWidgetItem(row.description or "")
            # description 만 편집 허용
            self.table.setItem(r, _COL_DESC, desc_item)
        self.table.blockSignals(False)
        self.error_label.setText("")

    def _on_add_clicked(self) -> None:
        token = self.add_label_input.text().strip()
        if not token:
            return
        try:
            self.registry.add_label(self.current_axis(), token)
        except LabelValidationError:
            self.error_label.setText(
                _tr("영문 소문자·숫자·`_` 만 가능 (예: pixel_art)")
            )
            return
        self.add_label_input.clear()
        self._refresh_table(self.current_axis())

    def _on_toggle_clicked(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        label_item = self.table.item(row, _COL_LABEL)
        state_item = self.table.item(row, _COL_STATE)
        if label_item is None or state_item is None:
            return
        label = label_item.text().lstrip("⚠ ").strip()
        currently_enabled = state_item.text() == _tr("활성")
        self.toggle_enabled_for(label, not currently_enabled)

    def _on_table_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != _COL_DESC:
            return
        label_item = self.table.item(item.row(), _COL_LABEL)
        if label_item is None:
            return
        label = label_item.text().lstrip("⚠ ").strip()
        new_desc = item.text() or None
        self.registry.set_description(self.current_axis(), label, new_desc)
        self._refresh_table(self.current_axis())
