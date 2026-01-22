from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel, QApplication
from PySide6.QtCore import Qt

from de4py.lang import tr
from de4py.lang.keys import MSG_COPIED, BTN_COPY_OUTPUT, LBL_OUTPUT



class OutputTextArea(QWidget):
    def __init__(self, title: str = None, show_copy: bool = True, parent=None):
        super().__init__(parent)
        self._title = title
        self._has_copy = show_copy
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        header_layout = QHBoxLayout()
        title = self._title if self._title is not None else tr(LBL_OUTPUT)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("OutputTitle")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        if self._has_copy:
            self.copy_btn = QPushButton(tr(BTN_COPY_OUTPUT))
            self.copy_btn.clicked.connect(self._copy_to_clipboard)
            header_layout.addWidget(self.copy_btn)
        
        layout.addLayout(header_layout)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)

    def _copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())
        main_window = self.window()
        if hasattr(main_window, 'show_notification'):
            main_window.show_notification("success", tr(MSG_COPIED))


    def set_text(self, text: str):
        self.text_edit.setPlainText(text)

    def append_text(self, text: str):
        self.text_edit.append(text)

    def clear(self):
        self.text_edit.clear()

    def get_text(self) -> str:
        return self.text_edit.toPlainText()

    def retranslate_ui(self):
        """Update strings on language change."""
        if self._title is None:
            self.title_label.setText(tr(LBL_OUTPUT))
        
        if self._has_copy:
            self.copy_btn.setText(tr(BTN_COPY_OUTPUT))
