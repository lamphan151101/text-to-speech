from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from speechmaapp.core.speechma_engine import fetch_captcha_image
from speechmaapp.utils.i18n import tr


class CaptchaDialog(QDialog):
    def __init__(self, parent=None, initial_image: bytes | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("captcha.title"))
        self.setModal(True)
        self.setMinimumWidth(340)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setMinimumSize(220, 70)

        self._refresh_btn = QPushButton(tr("captcha.refresh"))
        self._refresh_btn.clicked.connect(self._load_captcha)

        self._code_label = QLabel(tr("captcha.label"))
        self._code_input = QLineEdit()
        self._code_input.setMaxLength(10)
        self._code_input.setPlaceholderText("12345")

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #dc2626;")
        self._error_label.setVisible(False)
        self._error_label.setWordWrap(True)

        ok_btn = QPushButton(tr("captcha.ok"))
        ok_btn.setObjectName("primaryButton")
        cancel_btn = QPushButton(tr("captcha.cancel"))
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        img_row = QHBoxLayout()
        img_row.addWidget(self._image_label, 1)
        img_row.addWidget(self._refresh_btn)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.addLayout(img_row)
        layout.addWidget(self._code_label)
        layout.addWidget(self._code_input)
        layout.addWidget(self._error_label)
        layout.addLayout(btn_row)

        if initial_image:
            self._show_image(initial_image)
        else:
            self._load_captcha()

    def _load_captcha(self) -> None:
        try:
            data = fetch_captcha_image()
            self._show_image(data)
            self._error_label.setVisible(False)
        except Exception:
            self._error_label.setText(tr("captcha.network_error"))
            self._error_label.setVisible(True)

    def _show_image(self, data: bytes) -> None:
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        if not pixmap.isNull():
            self._image_label.setPixmap(pixmap)
        else:
            self._error_label.setText(tr("captcha.network_error"))
            self._error_label.setVisible(True)

    def show_wrong_code_error(self) -> None:
        self._error_label.setText(tr("captcha.error"))
        self._error_label.setVisible(True)
        self._code_input.clear()
        self._load_captcha()

    def get_code(self) -> str:
        return self._code_input.text().strip()
