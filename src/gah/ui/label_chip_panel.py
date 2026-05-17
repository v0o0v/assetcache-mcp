"""M4 — LabelChipPanel: 종류별 탭 + axis 칩 다중 선택 + AND/OR/NOT 모드 라디오.

LibraryView 좌측 사이드 패널.  ``selectionChanged`` 시그널이 칩 토글 / 모드
변경에서 발화 — 상위 위젯이 받아 검색 재호출.

종류 분류 (M4 follow-up 2026-05-17):
- ``sound_*`` axis → **사운드** 탭
- ``sheet_*`` axis → **스프라이트시트** 탭 (현재는 비어 있음, M5+ 가 채움)
- 그 외 → **스프라이트** 탭

매칭 모드 라디오는 탭 위에 1 줄로 둔다 (패널 전체 단위, 탭 무관).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QRadioButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.label_query import LabelFilter


if TYPE_CHECKING:  # pragma: no cover
    from ..core.labels import LabelRegistry


def _tr(text: str) -> str:
    return QCoreApplication.translate("LabelChipPanel", text)


_MODES = ("all", "any", "none")


def _classify_axis(axis_name: str) -> str:
    """axis 이름 → 탭 키 ('sprite'|'spritesheet'|'sound').

    분류 규칙:
    - ``sound_`` prefix → ``sound``
    - ``sheet_`` prefix → ``spritesheet``
    - 그 외 → ``sprite`` (시각 axes: category/style/palette/mood/...)
    """
    if axis_name.startswith("sound_"):
        return "sound"
    if axis_name.startswith("sheet_"):
        return "spritesheet"
    return "sprite"


_TAB_ORDER = (
    ("sprite", "스프라이트"),
    ("spritesheet", "스프라이트시트"),
    ("sound", "사운드"),
)


class LabelChipPanel(QWidget):
    """매칭 모드 (상단) + 종류별 탭 (본문) — 칩 선택은 탭 무관 단일 풀."""

    selectionChanged = Signal()

    def __init__(
        self, registry: "LabelRegistry", parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._registry = registry
        # (axis, label) → QCheckBox — 모든 탭의 체크박스 합집합.
        self._checks: dict[tuple[str, str], QCheckBox] = {}
        self._mode_radios: dict[str, QRadioButton] = {}
        self._mode_group = QButtonGroup(self)
        # 탭별 본문 호스트 위젯 (populate 시 재구성).
        self._tab_hosts: dict[str, QWidget] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        # ── 매칭 모드 — 상단 라디오 1 줄 (탭 위, 패널 전체 단위) ───────
        mode_box = QGroupBox(_tr("매칭 모드"))
        mb = QHBoxLayout(mode_box)
        for key, label in (("all", "AND"), ("any", "OR"), ("none", "NOT")):
            r = QRadioButton(label)
            self._mode_radios[key] = r
            self._mode_group.addButton(r)
            r.toggled.connect(self._on_radio_toggled)
            mb.addWidget(r)
        self._mode_radios["all"].setChecked(True)
        root.addWidget(mode_box)

        # ── QTabWidget — 종류별 탭 (sprite/spritesheet/sound) ────────
        self._tabs = QTabWidget(self)
        for key, title in _TAB_ORDER:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            host = QWidget()
            QVBoxLayout(host)   # populate 가 재구성
            self._tab_hosts[key] = host
            scroll.setWidget(host)
            self._tabs.addTab(scroll, _tr(title))
        root.addWidget(self._tabs)

        self.populate(registry)

    # -- public API ---------------------------------------------------

    def populate(self, registry: "LabelRegistry") -> None:
        """등록된 axis/label 로 탭별 칩 그리드 빌드 (재호출 시 clear+rebuild)."""
        # 기존 탭 본문 + 체크박스 모두 제거.
        self._checks.clear()
        for host in self._tab_hosts.values():
            layout = host.layout()
            # 기존 그룹박스 + stretch 제거.
            while layout.count():
                it = layout.takeAt(0)
                w = it.widget()
                if w is not None:
                    w.deleteLater()
        # axis 별로 분류 후 해당 탭 본문에 그룹박스 추가.
        for axis in registry.list_axes():
            labels = registry.list_labels(axis=axis, enabled_only=True)
            if not labels:
                continue
            host = self._tab_hosts[_classify_axis(axis)]
            group = QGroupBox(axis)
            hl = QHBoxLayout(group)
            for label in labels:
                cb = QCheckBox(label)
                cb.toggled.connect(self._on_check_toggled)
                self._checks[(axis, label)] = cb
                hl.addWidget(cb)
            host.layout().addWidget(group)
        # 마무리 stretch — 그룹박스가 위쪽으로 정렬되도록.
        for host in self._tab_hosts.values():
            host.layout().addStretch(1)

    def selected(self) -> tuple[str, list[LabelFilter]]:
        """현재 선택 — `(mode, [LabelFilter, ...])`. 탭 무관 단일 풀.

        mode ∈ {'all', 'any', 'none'}.
        """
        mode = self.mode()
        chosen = [
            LabelFilter(axis=ax, label=lbl)
            for (ax, lbl), cb in self._checks.items()
            if cb.isChecked()
        ]
        return mode, chosen

    def mode(self) -> str:
        for key, r in self._mode_radios.items():
            if r.isChecked():
                return key
        return "all"

    def set_mode(self, mode: str) -> None:
        if mode not in _MODES:
            return
        self._mode_radios[mode].setChecked(True)

    # -- internal -----------------------------------------------------

    def _on_check_toggled(self, _checked: bool) -> None:
        self.selectionChanged.emit()

    def _on_radio_toggled(self, _checked: bool) -> None:
        # 두 라디오가 toggled 시그널을 동시에 보내지만 (one ON, one OFF) —
        # 중복 발화 방지를 위해 ON 케이스만.
        if not _checked:
            return
        self.selectionChanged.emit()
