"""M4 — SearchSidePanel: 6 가중치 슬라이더 + 3 프리셋 + 저장된 검색 리스트.

LibraryView 우측 사이드 패널.  슬라이더가 ``Config.weight_*`` 와 양방향
바인딩 — 슬라이더 변경 시 즉시 Config 갱신.  저장된 검색은 ``Store`` 의
``saved_searches`` 테이블에서 가져온다.

M4 follow-up (2026-05-17):
- 우클릭 컨텍스트 메뉴 — "이름 수정" / "삭제"
- 저장 다이얼로그 — 이름 중복 감지 시 덮어쓰기 확인 다이얼로그
- 신호 시그니처 — ``saveCurrentRequested(str, bool)`` (overwrite 플래그)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


if TYPE_CHECKING:  # pragma: no cover
    from ..config import Config
    from ..core.store import Store


def _tr(text: str) -> str:
    return QCoreApplication.translate("SearchSidePanel", text)


_WEIGHT_FIELDS = (
    ("weight_semantic", "의미"),
    ("weight_keyword", "키워드"),
    ("weight_label_match", "라벨"),
    ("weight_consistency", "통일성"),
    ("weight_recency", "최신"),
    ("weight_feedback", "피드백"),
)


# Preset weights (합 1.00 유지) — M4 plan §3.6.
DEFAULT_M4_WEIGHTS = {
    "weight_semantic": 0.35,
    "weight_keyword": 0.10,
    "weight_label_match": 0.20,
    "weight_consistency": 0.20,
    "weight_recency": 0.05,
    "weight_feedback": 0.10,
}

CONSISTENCY_FIRST_WEIGHTS = {
    "weight_semantic": 0.25,
    "weight_keyword": 0.05,
    "weight_label_match": 0.10,
    "weight_consistency": 0.50,
    "weight_recency": 0.05,
    "weight_feedback": 0.05,
}

NOVELTY_FIRST_WEIGHTS = {
    "weight_semantic": 0.45,
    "weight_keyword": 0.10,
    "weight_label_match": 0.10,
    "weight_consistency": 0.05,
    "weight_recency": 0.20,
    "weight_feedback": 0.10,
}

_PRESETS = {
    "balanced": DEFAULT_M4_WEIGHTS,
    "consistency_first": CONSISTENCY_FIRST_WEIGHTS,
    "novelty_first": NOVELTY_FIRST_WEIGHTS,
}


class SearchSidePanel(QWidget):
    """6 슬라이더 + 3 프리셋 + 저장된 검색 (우클릭 메뉴) 패널."""

    weightsChanged = Signal()
    savedSearchActivated = Signal(str)                # (name)
    saveCurrentRequested = Signal(str, bool)          # (name, overwrite)
    savedSearchDeleteRequested = Signal(str)          # (name)
    savedSearchRenameRequested = Signal(str, str)     # (old_name, new_name)

    def __init__(
        self,
        config: "Config",
        store: "Store",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._store = store
        self._sliders: dict[str, QSlider] = {}
        self._suspend_slider_callback = False

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        # 가중치 슬라이더 (6 채널).
        sliders_box = QGroupBox(_tr("가중치"))
        sb_layout = QVBoxLayout(sliders_box)
        for name, label in _WEIGHT_FIELDS:
            row = QHBoxLayout()
            row.addWidget(QLabel(_tr(label)))
            s = QSlider(Qt.Horizontal)
            s.setRange(0, 100)
            s.setValue(int(getattr(config, name) * 100))
            s.valueChanged.connect(
                lambda v, fname=name: self._on_slider_changed(fname, v),
            )
            self._sliders[name] = s
            row.addWidget(s)
            sb_layout.addLayout(row)
        root.addWidget(sliders_box)

        # 프리셋 버튼 3개.
        preset_box = QGroupBox(_tr("프리셋"))
        pl = QHBoxLayout(preset_box)
        for key, label in (
            ("balanced", "균형"),
            ("consistency_first", "통일성 우선"),
            ("novelty_first", "참신성 우선"),
        ):
            b = QPushButton(_tr(label))
            b.clicked.connect(lambda _, k=key: self.apply_preset(k))
            pl.addWidget(b)
        root.addWidget(preset_box)

        # 저장된 검색 리스트 + 우클릭 컨텍스트 메뉴.
        root.addWidget(QLabel(_tr("저장된 검색")))
        self._saved_list = QListWidget(self)
        self._saved_list.itemDoubleClicked.connect(
            lambda it: self.savedSearchActivated.emit(it.text()),
        )
        self._saved_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._saved_list.customContextMenuRequested.connect(
            self._on_saved_list_context_menu,
        )
        root.addWidget(self._saved_list)

        # 저장 버튼.
        self._save_btn = QPushButton(_tr("현재 검색 저장…"))
        self._save_btn.clicked.connect(self._on_save_clicked)
        root.addWidget(self._save_btn)

    # -- public API for tests + integration ----------------------------

    def slider_value(self, name: str) -> int:
        return self._sliders[name].value()

    def set_slider_value(self, name: str, value: int) -> None:
        self._sliders[name].setValue(int(value))

    def apply_preset(self, key: str) -> None:
        weights = _PRESETS.get(key)
        if weights is None:
            return
        self._suspend_slider_callback = True
        try:
            for name, v in weights.items():
                self._sliders[name].setValue(int(v * 100))
                setattr(self._config, name, float(v))
        finally:
            self._suspend_slider_callback = False
        self.weightsChanged.emit()

    def reload_saved_searches(self, project_id: int | None) -> None:
        self._current_project_id = project_id
        self._saved_list.clear()
        rows = self._store.list_saved_searches(project_id)
        for row in rows:
            QListWidgetItem(row.name, self._saved_list)

    def saved_search_names(self) -> list[str]:
        return [
            self._saved_list.item(i).text()
            for i in range(self._saved_list.count())
        ]

    def activate_saved_search(self, name: str) -> None:
        """저장된 검색 더블클릭 동일 — 시그널 발화 헬퍼."""
        self.savedSearchActivated.emit(name)

    def name_exists(self, name: str) -> bool:
        """저장된 검색 이름 중복 감지 — production 다이얼로그 분기에 사용."""
        return self._store.get_saved_search(getattr(self, "_current_project_id", None),
                                              name) is not None

    def request_save_with_name(self, name: str) -> None:
        """다이얼로그 우회 — overwrite=False 로 emit (테스트 헬퍼)."""
        self.saveCurrentRequested.emit(name, False)

    def request_overwrite_save(self, name: str) -> None:
        """다이얼로그 우회 — overwrite=True 로 emit (테스트 헬퍼)."""
        self.saveCurrentRequested.emit(name, True)

    def request_delete(self, name: str) -> None:
        """다이얼로그 우회 — savedSearchDeleteRequested(name) (테스트 헬퍼)."""
        self.savedSearchDeleteRequested.emit(name)

    def request_rename(self, old_name: str, new_name: str) -> None:
        """다이얼로그 우회 — savedSearchRenameRequested(old, new) (테스트 헬퍼)."""
        self.savedSearchRenameRequested.emit(old_name, new_name)

    def bind_config(self, config: "Config") -> None:
        """Config 인스턴스 교체 — 슬라이더 값을 새 Config 기준으로 리프레시."""
        self._config = config
        self._suspend_slider_callback = True
        try:
            for name, _ in _WEIGHT_FIELDS:
                self._sliders[name].setValue(int(getattr(config, name) * 100))
        finally:
            self._suspend_slider_callback = False

    # -- internal -----------------------------------------------------

    def _on_slider_changed(self, name: str, value: int) -> None:
        if self._suspend_slider_callback:
            return
        new_v = value / 100.0
        setattr(self._config, name, new_v)
        self.weightsChanged.emit()

    def _on_save_clicked(self) -> None:
        # 1) 이름 입력 다이얼로그.
        text, ok = QInputDialog.getText(self, _tr("저장된 검색 이름"),
                                         _tr("이름:"))
        if not ok or not text.strip():
            return
        name = text.strip()
        # 2) 중복 감지 + 덮어쓰기 확인.
        if self.name_exists(name):
            reply = QMessageBox.question(
                self,
                _tr("이미 존재"),
                _tr("'{name}' 은 이미 존재합니다. 덮어쓸까요?").format(name=name),
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if reply != QMessageBox.Yes:
                return
            self.saveCurrentRequested.emit(name, True)
        else:
            self.saveCurrentRequested.emit(name, False)

    def _on_saved_list_context_menu(self, pos) -> None:
        """저장된 검색 리스트 우클릭 — 이름 수정 / 삭제 메뉴."""
        item = self._saved_list.itemAt(pos)
        if item is None:
            return
        name = item.text()
        menu = QMenu(self._saved_list)
        rename_act = QAction(_tr("이름 수정…"), menu)
        delete_act = QAction(_tr("삭제"), menu)
        menu.addAction(rename_act)
        menu.addAction(delete_act)
        chosen = menu.exec(self._saved_list.viewport().mapToGlobal(pos))
        if chosen is rename_act:
            self._prompt_rename(name)
        elif chosen is delete_act:
            self._prompt_delete(name)

    def _prompt_rename(self, old_name: str) -> None:
        new_name, ok = QInputDialog.getText(
            self,
            _tr("이름 수정"),
            _tr("새 이름:"),
            text=old_name,
        )
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name or new_name == old_name:
            return
        # 중복 감지 — UNIQUE 충돌은 store 가 잡아내지만 미리 안내가 친절.
        if self.name_exists(new_name):
            QMessageBox.warning(
                self,
                _tr("이미 존재"),
                _tr("'{name}' 이 이미 존재합니다. 다른 이름을 사용하세요.")
                    .format(name=new_name),
            )
            return
        self.savedSearchRenameRequested.emit(old_name, new_name)

    def _prompt_delete(self, name: str) -> None:
        reply = QMessageBox.question(
            self,
            _tr("삭제 확인"),
            _tr("'{name}' 을 삭제할까요?").format(name=name),
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if reply == QMessageBox.Yes:
            self.savedSearchDeleteRequested.emit(name)
