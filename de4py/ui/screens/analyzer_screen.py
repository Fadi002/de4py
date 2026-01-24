import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt

from de4py.ui.widgets.output_textarea import OutputTextArea
from de4py.ui.workers.analyzer_worker import AnalyzerWorker
from de4py.utils import sentry
import os
from de4py.lang import tr
from de4py.lang.keys import (
    SCREEN_TITLE_ANALYZER, ANALYZER_SELECT_FILE, ANALYZER_ANALYZE,
    ANALYZER_RESULTS, MSG_NO_FILE_SELECTED, MSG_OPERATION_COMPLETE,
    MSG_OPERATION_FAILED, MSG_WARNING, MSG_SUCCESS, MSG_ERROR, ANALYZER_OPTIONS_TITLE,
    ANALYZER_ONLY_EXE, ANALYZER_EXECUTED, ANALYZER_CMD_PACKER,
    ANALYZER_CMD_UNPACK, ANALYZER_CMD_SUS_STRINGS, ANALYZER_CMD_ALL_STRINGS,
    ANALYZER_CMD_HASHES
)



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
        
        self.title_label = QLabel(tr(SCREEN_TITLE_ANALYZER))
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        
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
        
        self.select_btn = QPushButton(tr(ANALYZER_SELECT_FILE))
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

        self.options_layout = QVBoxLayout(frame)
        self.options_layout.setSpacing(10)
        self.options_layout.setContentsMargins(20, 20, 20, 20)

        
        self.options_title = QLabel(tr(ANALYZER_OPTIONS_TITLE))
        self.options_title.setObjectName("ChangelogTitleLabel")
        self.options_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.options_title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.options_layout.addWidget(self.options_title)

        self._add_command_buttons(self.options_layout)
        
        return frame


    def _create_output_frame(self):
        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame.setMinimumHeight(360)
        
        layout = QVBoxLayout(frame)
        self.output = OutputTextArea(show_copy=True)
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
            sentry.breadcrumb(f"File selected for analysis: {filename}", category="user.action", path=file_path)

    def _run_command(self, command: str):
        if not self._file_path:
            self.window().show_notification("warning", tr(MSG_NO_FILE_SELECTED))
            return
        
        if command in ["detect_packer", "unpack_exe"] and not self._file_path.endswith(".exe"):
            self.window().show_notification("failure", tr(ANALYZER_ONLY_EXE))
            return

        
        with sentry.transaction("File Analysis", "tool.analyzer"):
            file_size = os.path.getsize(self._file_path) if os.path.exists(self._file_path) else 0
            sentry.set_extra_context("analyzer_meta", {
                "command": command,
                "file_path": self._file_path,
                "file_size": file_size
            })
            
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
        self.window().show_notification("success", tr(ANALYZER_EXECUTED))


    def _on_command_error(self, error: str):
        self.window().hide_loading()
        self.output.set_text(error)
        self.window().show_notification("failure", tr(MSG_OPERATION_FAILED))

    def retranslate_ui(self):
        """Update UI texts when language changes."""
        self.title_label.setText(tr(SCREEN_TITLE_ANALYZER))
        self.select_btn.setText(tr(ANALYZER_SELECT_FILE))
        self.options_title.setText(tr(ANALYZER_OPTIONS_TITLE))
        # We need to refresh the options frame to update command button texts
        while self.options_layout.count() > 1: # Keep the title
             item = self.options_layout.takeAt(1)
             if item.widget():
                 item.widget().deleteLater()
        
        self.output.retranslate_ui()
        
        self._add_command_buttons(self.options_layout)

    def _add_command_buttons(self, layout):
        commands = [
            (tr(ANALYZER_CMD_PACKER), "detect_packer"),
            (tr(ANALYZER_CMD_UNPACK), "unpack_exe"),
            (tr(ANALYZER_CMD_SUS_STRINGS), "sus_strings_lookup"),
            (tr(ANALYZER_CMD_ALL_STRINGS), "all_strings_lookup"),
            (tr(ANALYZER_CMD_HASHES), "get_file_hashs"),
        ]
        for label, cmd in commands:
            btn = QPushButton(label)
            btn.setFixedHeight(35)
            btn.clicked.connect(lambda checked, c=cmd: self._run_command(c))
            layout.addWidget(btn)
