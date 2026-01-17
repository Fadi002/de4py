from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt

from de4py.lang import tr
from de4py.lang.keys import (
    SCREEN_TITLE_DEOBFUSCATOR, DEOBF_SELECT_FILE, DEOBF_DEOBFUSCATE,
    MSG_NO_FILE_SELECTED, MSG_OPERATION_COMPLETE, MSG_OPERATION_FAILED,
    MSG_WARNING, MSG_SUCCESS, MSG_ERROR
)

from de4py.ui.widgets.output_textarea import OutputTextArea
from de4py.ui.workers.deobfuscator_worker import DeobfuscatorWorker


class DeobfuscatorScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_path = None
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(20)
        
        self.title_label = QLabel(tr(SCREEN_TITLE_DEOBFUSCATOR))
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        
        content_layout = QHBoxLayout()
        content_layout.setSpacing(40)
        
        left_frame = self._create_left_frame()
        content_layout.addWidget(left_frame)
        
        right_frame = self._create_right_frame()
        content_layout.addWidget(right_frame, 1)
        
        layout.addLayout(content_layout, 1)

    def _create_left_frame(self):
        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame.setFixedWidth(350) 
        frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Maximum)
    
        layout = QVBoxLayout(frame)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter) 
        layout.setContentsMargins(20, 20, 20, 20)
    
        self.select_btn = QPushButton(tr(DEOBF_SELECT_FILE))
        self.select_btn.clicked.connect(self._on_select_file)
        self.select_btn.setFixedHeight(35)
        layout.addWidget(self.select_btn)

        self.file_label = QLabel("None")
        self.file_label.setObjectName("FilePathLabel") 
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_label.setFixedHeight(30)
        self.file_label.setWordWrap(True)

        layout.addWidget(self.file_label)
    
        layout.addStretch()
    
        self.deobf_btn = QPushButton(tr(DEOBF_DEOBFUSCATE))
        self.deobf_btn.setMinimumWidth(120)
        self.deobf_btn.clicked.connect(self._on_deobfuscate)
        layout.addWidget(self.deobf_btn, alignment=Qt.AlignmentFlag.AlignCenter)
    
        return frame
    
    def _create_right_frame(self):
        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame.setMinimumHeight(350)
        
        layout = QVBoxLayout(frame)
        
        self.output = OutputTextArea("Output:", show_copy=True)
        layout.addWidget(self.output)
        
        return frame

    def _on_select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "",
            "Python Files (*.py);;Python Compiled (*.pyc);;Exe Files (*.exe);;All Files (*.*)"
        )
        if file_path:
            self._file_path = file_path
            filename = file_path.split("/")[-1].split("\\")[-1]
            self.file_label.setText(filename)

    def _on_deobfuscate(self):
        if not self._file_path:
            self.window().show_notification("warning", tr(MSG_NO_FILE_SELECTED))
            return
        
        self.window().show_loading()
        
        self._worker = DeobfuscatorWorker(self._file_path, self)
        self._worker.finished.connect(self._on_deobf_finished)
        self._worker.error.connect(self._on_deobf_error)
        self._worker.start()

    def _on_deobf_finished(self, result: str):
        self.window().hide_loading()
        self.output.set_text(result)
        self.output.set_text(result)
        self.window().show_notification("success", tr(MSG_OPERATION_COMPLETE))

    def _on_deobf_error(self, error: str):
        self.window().hide_loading()
        self.output.set_text(error)
        self.window().show_notification("failure", tr(MSG_OPERATION_FAILED))

    def retranslate_ui(self):
        """Update UI texts when language changes."""
        self.title_label.setText(tr(SCREEN_TITLE_DEOBFUSCATOR))
        self.select_btn.setText(tr(DEOBF_SELECT_FILE))
        self.deobf_btn.setText(tr(DEOBF_DEOBFUSCATE))
