import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt

from de4py.ui.widgets.output_textarea import OutputTextArea
from de4py.ui.workers.analyzer_worker import AnalyzerWorker


class AnalyzerScreen(QWidget):
    """
    UI component for static file analysis.
    Provides options to detect packers, calculate hashes, unpack files,
    and search for suspicious strings or extract all strings.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_path = None
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(20)
        
        title = QLabel("ANALYZER")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        
        left_layout = QVBoxLayout()
        left_layout.setSpacing(20)
        
        file_frame = self._create_file_frame()
        left_layout.addWidget(file_frame)
        
        options_frame = self._create_options_frame()
        left_layout.addWidget(options_frame)
        
        left_layout.addStretch()
        content_layout.addLayout(left_layout)
        
        output_frame = self._create_output_frame()
        content_layout.addWidget(output_frame, 1)
        
        layout.addLayout(content_layout, 1)

    def _create_file_frame(self):
        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame.setFixedWidth(390)
        frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Maximum)
        
        layout = QVBoxLayout(frame)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.select_btn = QPushButton("Select a file")
        self.select_btn.setFixedHeight(35)
        self.select_btn.clicked.connect(self._on_select_file)
        layout.addWidget(self.select_btn)
        
        self.file_label = QLabel("None")
        self.file_label.setObjectName("FilePathLabel")
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_label.setFixedHeight(30)
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)
        
        return frame

    def _create_options_frame(self):
        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame.setMinimumWidth(390)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(frame)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title_label = QLabel("ANALYSIS OPTIONS")
        title_label.setObjectName("ChangelogTitleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout.addWidget(title_label)
        
        commands = [
            ("exe packer detector", "detect_packer"),
            ("unpack exe", "unpack_exe"),
            ("sus strings lookup", "sus_strings_lookup"),
            ("all strings lookup", "all_strings_lookup"),
            ("get file hashs", "get_file_hashs"),
        ]
        
        for label, cmd in commands:
            btn = QPushButton(label)
            btn.setFixedHeight(35)
            btn.clicked.connect(lambda checked, c=cmd: self._run_command(c))
            layout.addWidget(btn)
        
        return frame

    def _create_output_frame(self):
        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame.setMinimumHeight(360)
        
        layout = QVBoxLayout(frame)
        self.output = OutputTextArea("Output:", show_copy=True)
        layout.addWidget(self.output)
        
        return frame

    def _on_select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "",
            "Exe Files (*.exe);;All Files (*.*)"
        )
        if file_path:
            self._file_path = file_path
            filename = file_path.split("/")[-1].split("\\")[-1]
            self.file_label.setText(filename)

    def _run_command(self, command: str):
        if not self._file_path:
            self.window().show_notification("warning", "Select a file first")
            return
        
        if command in ["detect_packer", "unpack_exe"] and not self._file_path.endswith(".exe"):
            self.window().show_notification("failure", "only exe files are supported")
            return
        
        self.window().show_loading()
        
        self._worker = AnalyzerWorker(command, self._file_path, self)
        self._worker.finished.connect(self._on_command_finished)
        self._worker.error.connect(self._on_command_error)
        self._worker.start()

    def _on_command_finished(self, result: str):
        self.window().hide_loading()
        
        if result.startswith("{") or result.startswith("["):
            try:
                parsed = json.loads(result)
                result = json.dumps(parsed, indent=2)
            except Exception:
                pass
        
        self.output.set_text(result)
        self.window().show_notification("success", "Command executed")

    def _on_command_error(self, error: str):
        self.window().hide_loading()
        self.output.set_text(error)
        self.window().show_notification("failure", "Command failed")
