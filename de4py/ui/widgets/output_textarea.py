from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel, QApplication
from PySide6.QtCore import Qt

from de4py.lang import tr
from de4py.lang.keys import MSG_COPIED



class OutputTextArea(QWidget):
    def __init__(self, title: str = "Output:", show_copy: bool = True, parent=None):
        super().__init__(parent)
        self._setup_ui(title, show_copy)

    def _setup_ui(self, title: str, show_copy: bool):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        header_layout = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("OutputTitle")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        if show_copy:
            self.copy_btn = QPushButton("Copy Output")
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
