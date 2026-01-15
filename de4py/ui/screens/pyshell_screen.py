import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QLineEdit, QGridLayout, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt, Signal

from de4py.ui.widgets.output_textarea import OutputTextArea
from de4py.ui.widgets.modal_overlay import ModalOverlay
from de4py.ui.workers.pyshell_worker import (
    InjectionWorker, PipeCommandWorker,
    ShowConsoleWorker, ProcessMonitorWorker
)
from de4py.ui.constants import SPACING_MD
from de4py.ui.controllers import pyshell_controller
from de4py.utils import gen_path


class PyShellScreen(QWidget):
    process_died = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._injected = False
        self._analyzer_handle = False
        self._workers = []
        self._process_monitor = None
        self._setup_ui()

    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(20)

        title = QLabel("PYSHELL")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        left_layout = QVBoxLayout()
        left_layout.setSpacing(20)

        inject_frame = self._create_inject_frame()
        left_layout.addWidget(inject_frame)
        left_layout.addStretch()

        output_frame = self._create_output_frame()

        content_layout.addLayout(left_layout)
        content_layout.addWidget(output_frame)

        content_layout.setStretch(0, 0)  # left panel fixed
        content_layout.setStretch(1, 1)  # output expands

        layout.addLayout(content_layout)

        commands_frame = self._create_commands_frame()
        layout.addWidget(commands_frame)

        self._create_modal()

    # ------------------------------------------------------------------

    def _create_inject_frame(self):
        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame.setFixedWidth(390)
        frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        layout = QVBoxLayout(frame)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        pid_layout = QHBoxLayout()
        pid_label = QLabel("Target pid:")
        self.pid_input = QLineEdit()
        self.pid_input.setPlaceholderText("Enter PID")

        pid_layout.addWidget(pid_label)
        pid_layout.addWidget(self.pid_input)
        layout.addLayout(pid_layout)

        btn_layout = QHBoxLayout()

        self.inject_btn = QPushButton("Inject")
        self.inject_btn.setFixedHeight(35)
        self.inject_btn.clicked.connect(lambda: self._inject("normal"))
        btn_layout.addWidget(self.inject_btn)

        self.stealth_btn = QPushButton("Stealth Inject")
        self.stealth_btn.setFixedHeight(35)
        self.stealth_btn.clicked.connect(lambda: self._inject("stealth"))
        btn_layout.addWidget(self.stealth_btn)

        layout.addLayout(btn_layout)
        return frame

    # ------------------------------------------------------------------

    def _create_output_frame(self):
        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame.setMinimumHeight(180)
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Uses built-in themed title instead of manual label
        self.output = OutputTextArea("OUTPUT:", show_copy=True)
        self.output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.output)
        
        return frame

    # ------------------------------------------------------------------

    def _create_commands_frame(self):
        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title_label = QLabel("COMMANDS")
        title_label.setObjectName("ChangelogTitleLabel")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        grid = QGridLayout()
        grid.setSpacing(10)

        for i in range(4):
            grid.setColumnStretch(i, 1)

        commands = [
            ("exec py code", "ExecPY"),
            ("crash process", "ForceCrash"),
            ("get all functions", "GetFunctions"),
            ("force show console", "ShowConsole"),
            ("Pyshell (tkinter GUI)", "PyshellGUI"),
            ("Dump strings", "DumpStrings"),
            ("Remove exit function", "delExit"),
            ("Deattach DLL", "DeattachDLL"),
            ("Behavior Monitoring", "GetAnalyzerHandle"),
        ]

        row = col = 0
        for label, cmd in commands:
            btn = QPushButton(label)
            btn.setFixedHeight(35)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda _, c=cmd: self._exec_command(c))

            grid.addWidget(btn, row, col)
            col += 1
            if col >= 4:
                col = 0
                row += 1

        layout.addLayout(grid)
        return frame

    # ------------------------------------------------------------------

    def _create_modal(self):
        self.show_console_modal = ModalOverlay(
            "Force Show Console",
            "Target pid:",
            "unhide console",
            self.window()
        )
        self.show_console_modal.submitted.connect(self._on_show_console)
        self.show_console_modal.hide()

    # ------------------------------------------------------------------
    # ------------------------- LOGIC UNCHANGED -------------------------
    # ------------------------------------------------------------------

    def _inject(self, inject_type: str):
        pid = self.pid_input.text().strip()
        if not pid:
            self.window().show_notification("warning", "Type process id first")
            return

        self.window().show_loading()
        stealth = inject_type == "stealth"

        worker = InjectionWorker(pid, stealth, self)
        worker.finished.connect(self._on_inject_finished)
        worker.error.connect(self._on_inject_error)
        worker.start()
        self._workers.append(worker)

    def _on_inject_finished(self, handle, success: bool):
        self.window().hide_loading()
        if success:
            self._injected = True
            self.output.set_text("pyshell injected")
            self.window().show_notification("success", "pyshell injector function executed")

            try:
                pid = int(self.pid_input.text().strip())
                self._process_monitor = ProcessMonitorWorker(pid, self)
                self._process_monitor.process_died.connect(self._on_process_died)
                self._process_monitor.start()
            except ValueError:
                pass
        else:
            self.output.set_text("Failed to inject")
            self.window().show_notification("failure", "pyshell injector function failed")

    def _on_inject_error(self, error: str):
        self.window().hide_loading()
        self.output.set_text(f"failed to inject pyshell: {error}")
        self.window().show_notification("failure", "pyshell injector function failed")

    def _on_process_died(self):
        self._injected = False
        self._analyzer_handle = False
        pyshell_controller.clear_handles()
        self.window().show_notification("warning", "Process crashed/died/killed")
        self.process_died.emit()

    def _exec_command(self, command: str):
        if command == "ShowConsole":
            self.show_console_modal.setParent(self.window())
            self.show_console_modal.fade_in()
            self.show_console_modal.raise_()
            return

        if not self._injected:
            self.window().show_notification("failure", "Please inject the dll into a process first")
            return

        if command in ("DumpStrings", "GetFunctions"):
            path, filename = gen_path()
            worker = PipeCommandWorker(f"{command}||{path}", self)
            worker.finished.connect(lambda _: self._on_command_result(f"saved as {filename}"))
            worker.start()
            self._workers.append(worker)

        elif command == "ExecPY":
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Python File", "", "Python Files (*.py)"
            )
            if file_path:
                worker = PipeCommandWorker(f"ExecPY||{file_path}", self)
                worker.finished.connect(lambda _: self._on_command_result("Executed"))
                worker.start()
                self._workers.append(worker)

        elif command == "GetAnalyzerHandle":
            if not self._analyzer_handle:
                pyshell_controller.write_to_pipe("GetAnalyzerHandle")
                pyshell_controller.open_analyzer_handle()
                self._analyzer_handle = True
                self.output.set_text("Executed | click the button again to open the menu")
                self.window().show_notification("success", "Command executed")
            else:
                self.window().navigate_to_behavior_monitor()

        elif command == "DeattachDLL":
            self._injected = False
            self._analyzer_handle = False
            worker = PipeCommandWorker(command, self)
            worker.finished.connect(lambda _: self._on_command_result("DLL detached"))
            worker.start()
            self._workers.append(worker)

        else:
            worker = PipeCommandWorker(command, self)
            worker.finished.connect(lambda _: self._on_command_result("Command executed"))
            worker.start()
            self._workers.append(worker)

    def _on_command_result(self, message: str):
        self.output.set_text(message)
        self.window().show_notification("success", "Command executed")

    def _on_show_console(self, pid: str):
        worker = ShowConsoleWorker(pid, self)
        worker.finished.connect(self._on_show_console_result)
        worker.start()
        self._workers.append(worker)

    def _on_show_console_result(self, success: bool):
        self.output.set_text("DONE" if success else "FAILED")
        self.window().show_notification(
            "success" if success else "failure", "Command executed"
        )
