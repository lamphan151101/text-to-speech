from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from speechmaapp.core.speaker_assignment import check_overlap, parse_segment_ranges
from speechmaapp.core.voices_catalog import ALL_LANGUAGES
from speechmaapp.models.speaker import Speaker
from speechmaapp.utils.i18n import tr, translator
from speechmaapp.utils.logging_utils import log_info


class SpeakerManager(QWidget):
    speakers_changed = Signal()
    preview_voice_requested = Signal(str, str, int, int)  # text, voice, pitch, rate

    def __init__(self) -> None:
        super().__init__()
        self.speakers: dict[str, Speaker] = {}
        self.max_index = 0
        self.voice_groups: dict = {}
        self.txt_mode = False

        self.name_input = QLineEdit()
        self.range_input = QLineEdit()
        self.language_combo = QComboBox()
        self.voice_combo = QComboBox()

        self.pitch_spinbox = QSpinBox()
        self.pitch_spinbox.setRange(-100, 100)
        self.pitch_spinbox.setValue(0)

        self.rate_spinbox = QSpinBox()
        self.rate_spinbox.setRange(-100, 100)
        self.rate_spinbox.setValue(0)

        self.mode_hint = QLabel("")
        self.name_label = QLabel()
        self.range_label = QLabel()
        self.language_label = QLabel()
        self.voice_label = QLabel()
        self.pitch_label = QLabel()
        self.rate_label = QLabel()

        self.table = QTableWidget(0, 4)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._load_selected_to_form)

        self.add_btn = QPushButton()
        self.remove_btn = QPushButton()
        self.preview_btn = QPushButton()
        self.add_btn.setObjectName("primaryButton")
        self.add_btn.clicked.connect(self.upsert_speaker)
        self.remove_btn.clicked.connect(self.delete_selected)
        self.preview_btn.clicked.connect(self.preview_voice)
        self.language_combo.currentTextChanged.connect(self._populate_voices)
        self.voice_combo.currentIndexChanged.connect(self._on_voice_params_changed)
        self.pitch_spinbox.valueChanged.connect(self._on_voice_params_changed)
        self.rate_spinbox.valueChanged.connect(self._on_voice_params_changed)

        self.voice_section_title = QLabel()
        self.voice_section_title.setObjectName("sectionTitle")
        self.mapping_section_title = QLabel()
        self.mapping_section_title.setObjectName("sectionTitle")
        self.separator = QFrame()
        self.separator.setFrameShape(QFrame.HLine)
        self.separator.setStyleSheet("color: #e2e8f0;")

        pitch_rate_row = QHBoxLayout()
        pitch_rate_row.setContentsMargins(0, 0, 0, 0)
        pitch_rate_row.setSpacing(6)
        pitch_rate_row.addWidget(self.pitch_label)
        pitch_rate_row.addWidget(self.pitch_spinbox)
        pitch_rate_row.addSpacing(8)
        pitch_rate_row.addWidget(self.rate_label)
        pitch_rate_row.addWidget(self.rate_spinbox)
        pitch_rate_widget = QWidget()
        pitch_rate_widget.setLayout(pitch_rate_row)

        self.top_form = QFormLayout()
        self.top_form.setContentsMargins(0, 0, 0, 0)
        self.top_form.setSpacing(6)
        self.top_form.addRow(self.name_label, self.name_input)
        self.top_form.addRow(self.range_label, self.range_input)
        self.top_form.addRow(self.language_label, self.language_combo)
        self.top_form.addRow(self.voice_label, self.voice_combo)
        self.top_form.addRow("", pitch_rate_widget)
        self.top_form.addRow("", self.mode_hint)

        voice_action_layout = QHBoxLayout()
        voice_action_layout.setContentsMargins(0, 0, 0, 0)
        voice_action_layout.setSpacing(8)
        voice_action_layout.addWidget(self.preview_btn)
        voice_action_layout.addStretch(1)
        voice_action_layout.addWidget(self.add_btn)

        list_action_layout = QHBoxLayout()
        list_action_layout.setContentsMargins(0, 0, 0, 0)
        list_action_layout.setSpacing(8)
        list_action_layout.addStretch(1)
        list_action_layout.addWidget(self.remove_btn)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(6)
        self.main_layout.addWidget(self.voice_section_title)
        self.main_layout.addLayout(self.top_form)
        self.main_layout.addLayout(voice_action_layout)
        self.main_layout.addWidget(self.separator)
        self.main_layout.addWidget(self.mapping_section_title)
        self.main_layout.addLayout(list_action_layout)
        self.main_layout.addWidget(self.table, 1)
        self.txt_spacer = QWidget()
        self.txt_spacer.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.txt_spacer.setVisible(False)
        self.main_layout.addWidget(self.txt_spacer)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.mode_hint.setWordWrap(True)
        translator.language_changed.connect(self.retranslate_ui)
        self.retranslate_ui()

    def set_max_index(self, max_index: int) -> None:
        self.max_index = max_index

    def set_voice_groups(self, grouped: dict, preferred_group: str = "") -> None:
        self.voice_groups = grouped
        self._rebuild_language_combo(preferred_group)

    def _rebuild_language_combo(self, preferred_group: str = "") -> None:
        current_key = str(self.language_combo.currentData() or "")
        self.language_combo.blockSignals(True)
        self.language_combo.clear()
        for group in self.voice_groups:
            label = tr("language.all") if group == ALL_LANGUAGES else group
            self.language_combo.addItem(label, group)
        target_key = preferred_group or current_key
        if target_key:
            idx = self.language_combo.findData(target_key)
            if idx >= 0:
                self.language_combo.setCurrentIndex(idx)
        elif self.language_combo.count() > 0:
            self.language_combo.setCurrentIndex(0)
        self.language_combo.blockSignals(False)
        self._populate_voices()

    def current_language_group(self) -> str:
        return str(self.language_combo.currentData() or self.language_combo.currentText())

    def set_txt_mode(self, enabled: bool) -> None:
        self.txt_mode = enabled
        self._set_field_collapsed(self.name_label, self.name_input, enabled)
        self._set_field_collapsed(self.range_label, self.range_input, enabled)
        self.add_btn.setVisible(not enabled)
        self.remove_btn.setVisible(not enabled)
        self.mapping_section_title.setVisible(not enabled)
        self.separator.setVisible(not enabled)
        self.table.setVisible(not enabled)
        self.txt_spacer.setVisible(enabled)
        self.mode_hint.setText(tr("speaker.txt_mode_hint") if enabled else "")
        if enabled:
            self._apply_txt_voice_settings()

    def _set_field_collapsed(self, label_widget: QLabel, field_widget: QWidget, collapsed: bool) -> None:
        label_widget.setVisible(not collapsed)
        field_widget.setVisible(not collapsed)
        if collapsed:
            label_widget.setMaximumHeight(0)
            field_widget.setMaximumHeight(0)
        else:
            label_widget.setMaximumHeight(16777215)
            field_widget.setMaximumHeight(16777215)

    def apply_txt_voice_settings(self) -> None:
        self._apply_txt_voice_settings()

    def preview_voice(self) -> None:
        voice = self.voice_combo.currentData()
        if not voice:
            QMessageBox.warning(self, tr("speaker.warn_title"), tr("speaker.warn_no_voice"))
            return
        self.preview_voice_requested.emit(
            tr("speaker.preview_sample_text"),
            str(voice),
            self.pitch_spinbox.value(),
            self.rate_spinbox.value(),
        )

    def upsert_speaker(self) -> None:
        if self.txt_mode:
            self._apply_txt_voice_settings()
            return
        name = self.name_input.text().strip()
        ranges = self.range_input.text().strip()
        if not name:
            QMessageBox.warning(self, tr("speaker.warn_title"), tr("speaker.warn_empty_name"))
            return
        try:
            segments = parse_segment_ranges(ranges, self.max_index)
        except ValueError as exc:
            QMessageBox.warning(self, tr("speaker.warn_title"), str(exc))
            return

        speaker = self.speakers.get(name, Speaker(name=name))
        speaker.segments = segments
        speaker.voice = self.voice_combo.currentData() or ""
        speaker.language_group = self.current_language_group()
        speaker.pitch = self.pitch_spinbox.value()
        speaker.rate = self.rate_spinbox.value()
        if not speaker.voice:
            QMessageBox.warning(self, tr("speaker.warn_title"), tr("speaker.warn_no_voice"))
            return
        self.speakers[name] = speaker
        log_info(
            f"Upsert speaker name={name} segments={sorted(segments)} "
            f"voice={speaker.voice} pitch={speaker.pitch} rate={speaker.rate}"
        )
        self.refresh()

    def delete_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        name_item = self.table.item(row, 0)
        if not name_item:
            return
        self.speakers.pop(name_item.text(), None)
        log_info(f"Deleted speaker name={name_item.text()}")
        self.refresh()

    def refresh(self) -> None:
        overlaps = check_overlap({name: sp.segments for name, sp in self.speakers.items()})
        if overlaps:
            QMessageBox.warning(
                self,
                tr("speaker.overlap_title"),
                tr("speaker.overlap_msg", items=", ".join(str(i) for i in sorted(overlaps))),
            )
        self.table.setRowCount(0)
        for speaker in self.speakers.values():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(speaker.name))
            self.table.setItem(row, 1, QTableWidgetItem(_compress_ranges(speaker.segments)))
            lang_display = tr("language.all") if speaker.language_group == ALL_LANGUAGES else speaker.language_group
            self.table.setItem(row, 2, QTableWidgetItem(lang_display))
            self.table.setItem(row, 3, QTableWidgetItem(speaker.voice))
        self.speakers_changed.emit()

    def _populate_voices(self) -> None:
        language = str(self.language_combo.currentData() or self.language_combo.currentText())
        current_voice = self.voice_combo.currentData()
        self.voice_combo.clear()
        for voice in self.voice_groups.get(language, []):
            hd = " [HD]" if voice.language == "Multilingual" else ""
            label = f"{voice.name} ({voice.country}) [{voice.gender}]{hd}"
            self.voice_combo.addItem(label, voice.voice_id)
        if current_voice:
            idx = self.voice_combo.findData(current_voice)
            if idx >= 0:
                self.voice_combo.setCurrentIndex(idx)

    def _load_selected_to_form(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        name_item = self.table.item(row, 0)
        if not name_item:
            return
        speaker = self.speakers.get(name_item.text())
        if not speaker:
            return
        self.name_input.setText(speaker.name)
        self.range_input.setText(_compress_ranges(speaker.segments))
        if speaker.language_group:
            lang_idx = self.language_combo.findData(speaker.language_group)
            if lang_idx >= 0:
                self.language_combo.setCurrentIndex(lang_idx)
        if speaker.voice:
            voice_idx = self.voice_combo.findData(speaker.voice)
            if voice_idx >= 0:
                self.voice_combo.setCurrentIndex(voice_idx)
        self.pitch_spinbox.setValue(speaker.pitch)
        self.rate_spinbox.setValue(speaker.rate)

    def _on_voice_params_changed(self) -> None:
        if self.txt_mode:
            self._apply_txt_voice_settings()

    def _apply_txt_voice_settings(self) -> None:
        voice = self.voice_combo.currentData() or ""
        if not voice:
            return
        speaker = self.speakers.get("TXT", Speaker(name="TXT"))
        speaker.segments = set(range(1, self.max_index + 1))
        speaker.voice = voice
        speaker.language_group = self.current_language_group()
        speaker.pitch = self.pitch_spinbox.value()
        speaker.rate = self.rate_spinbox.value()
        self.speakers["TXT"] = speaker
        log_info(
            f"TXT mode apply voice={speaker.voice} segments={len(speaker.segments)} "
            f"pitch={speaker.pitch} rate={speaker.rate}"
        )
        self.speakers_changed.emit()

    def retranslate_ui(self) -> None:
        self.name_label.setText(tr("speaker.name_label"))
        self.range_label.setText(tr("speaker.range_label"))
        self.language_label.setText(tr("speaker.language_label"))
        self.voice_label.setText(tr("speaker.voice_label"))
        self.pitch_label.setText(tr("speaker.pitch_label"))
        self.rate_label.setText(tr("speaker.rate_label"))
        self.pitch_spinbox.setToolTip(tr("speaker.pitch_tip"))
        self.rate_spinbox.setToolTip(tr("speaker.rate_tip"))
        self.add_btn.setText(tr("speaker.add_btn"))
        self.remove_btn.setText(tr("speaker.remove_btn"))
        self.preview_btn.setText(tr("speaker.preview_btn"))
        self.voice_section_title.setText(tr("section.voice_setup"))
        self.mapping_section_title.setText(tr("section.speaker_list"))
        self.table.setHorizontalHeaderLabels([
            tr("table.speaker"), tr("speaker.range_label"),
            tr("speaker.language_label"), tr("table.voice"),
        ])
        self.mode_hint.setText(tr("speaker.txt_mode_hint") if self.txt_mode else "")
        self._rebuild_language_combo()
        self.refresh()


def _compress_ranges(values: set[int]) -> str:
    if not values:
        return ""
    ordered = sorted(values)
    ranges: list[str] = []
    start = ordered[0]
    prev = ordered[0]
    for value in ordered[1:]:
        if value == prev + 1:
            prev = value
            continue
        ranges.append(f"{start}-{prev}" if start != prev else str(start))
        start = prev = value
    ranges.append(f"{start}-{prev}" if start != prev else str(start))
    return ",".join(ranges)
