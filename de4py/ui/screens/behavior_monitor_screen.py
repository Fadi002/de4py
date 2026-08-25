# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import os
import random
import string
import zlib
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QCheckBox
)
from PySide6.QtCore import Qt

from de4py.ui.widgets.output_textarea import OutputTextArea
from de4py.ui.workers.behavior_monitor_worker import BehaviorMonitorWorker
from de4py.ui.workers.pyshell_worker import PipeCommandWorker
from de4py.lang import tr
from de4py.lang.keys import (
    SCREEN_TITLE_BEHAVIOR, BM_MONITOR_OPTIONS, BM_MONITOR_FILES,
    BM_MONITOR_PROCESSES, BM_MONITOR_CONNECTIONS, BM_DUMP_SOCKET,
    BM_DUMP_SSL, BM_PYC_DUMPER, BM_BACK_TO_MENU,
    BM_FILES_HOOK_ON, BM_FILES_HOOK_OFF, BM_PROCS_HOOK_ON,
    BM_PROCS_HOOK_OFF, BM_CONN_HOOK_ON, BM_CONN_HOOK_OFF,
    BM_SOCKET_DUMP_ON, BM_SOCKET_DUMP_OFF, BM_SSL_DUMP_ON,
    BM_SSL_DUMP_OFF, BM_PYC_DUMP_ON, BM_PYC_DUMP_OFF, MSG_PIPE_FAILED
)


class BehaviorMonitorScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._monitor_worker = None
        self._pipe_workers = []
        self._setup_ui()
        self._connect_signals()
        self.output.set_streaming_limit(5000)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(20)

        self.title_label = QLabel(tr(SCREEN_TITLE_BEHAVIOR))
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(40)

        left_frame = self._create_checkboxes_frame()
        content_layout.addWidget(left_frame)

        right_frame = self._create_output_frame()
        content_layout.addWidget(right_frame, 1)

        layout.addLayout(content_layout, 1)

    def _create_checkboxes_frame(self):
        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame.setFixedWidth(390)

        layout = QVBoxLayout(frame)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        self.options_title = QLabel(tr(BM_MONITOR_OPTIONS))
        self.options_title.setObjectName("ChangelogTitleLabel")
        self.options_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.options_title)

        self.mf_checkbox = QCheckBox(tr(BM_MONITOR_FILES))
        layout.addWidget(self.mf_checkbox)

        self.mp_checkbox = QCheckBox(tr(BM_MONITOR_PROCESSES))
        layout.addWidget(self.mp_checkbox)

        mc_layout = QHBoxLayout()
        self.mc_checkbox = QCheckBox(tr(BM_MONITOR_CONNECTIONS))
        mc_layout.addWidget(self.mc_checkbox)
        self.dump_socket_checkbox = QCheckBox(tr(BM_DUMP_SOCKET))
        self.dump_socket_checkbox.setEnabled(False)
        mc_layout.addWidget(self.dump_socket_checkbox)
        layout.addLayout(mc_layout)

        self.ssl_checkbox = QCheckBox(tr(BM_DUMP_SSL))
        layout.addWidget(self.ssl_checkbox)

        self.pyc_checkbox = QCheckBox(tr(BM_PYC_DUMPER))
        layout.addWidget(self.pyc_checkbox)

        layout.addStretch()

        self.back_btn = QPushButton(tr(BM_BACK_TO_MENU))
        self.back_btn.setFixedHeight(35)
        self.back_btn.clicked.connect(self._go_back)
        layout.addWidget(self.back_btn)

        return frame

    def _create_output_frame(self):
        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame.setMinimumHeight(360)

        layout = QVBoxLayout(frame)
        self.output = OutputTextArea(show_copy=True)
        layout.addWidget(self.output)

        return frame

    def _connect_signals(self):
        self.mf_checkbox.stateChanged.connect(self._on_monitor_files)
        self.mp_checkbox.stateChanged.connect(self._on_monitor_processes)
        self.mc_checkbox.stateChanged.connect(self._on_monitor_connections)
        self.dump_socket_checkbox.stateChanged.connect(self._on_dump_socket)
        self.ssl_checkbox.stateChanged.connect(self._on_dump_ssl)
        self.pyc_checkbox.stateChanged.connect(self._on_pyc_dumper)

        from de4py.utils import sentry
        self.mf_checkbox.toggled.connect(lambda checked: sentry.breadcrumb(f"Monitor Files toggled: {checked}", category="user.action"))
        self.mp_checkbox.toggled.connect(lambda checked: sentry.breadcrumb(f"Monitor Processes toggled: {checked}", category="user.action"))
        self.mc_checkbox.toggled.connect(lambda checked: sentry.breadcrumb(f"Monitor Connections toggled: {checked}", category="user.action"))
        self.ssl_checkbox.toggled.connect(lambda checked: sentry.breadcrumb(f"SSL Dump toggled: {checked}", category="user.action"))
        self.pyc_checkbox.toggled.connect(lambda checked: sentry.breadcrumb(f"PYC Dumper toggled: {checked}", category="user.action"))

    def _add_output(self, text: str):
        self.output.append_text(text)

    def _create_dump_file(self, filename: str) -> str:
        dump_path = os.path.join(os.getcwd(), filename)
        if not os.path.exists(dump_path):
            with open(dump_path, 'w'):
                pass
        return dump_path

    def _send_pipe_command(self, command, box, success_msg):
        """Run a pipe command off the GUI thread. On failure the checkbox is
        reverted (without re-emitting) so its state always matches reality."""
        box.setEnabled(False)
        worker = PipeCommandWorker(command, self)
        self._pipe_workers.append(worker)

        def _done(result):
            box.setEnabled(True)
            if result == "OK.":
                self._add_output(success_msg)
            else:
                self._add_output(result)
            self._prune_pipe_workers()

        def _fail(err):
            box.setEnabled(True)
            box.blockSignals(True)
            box.setChecked(False)
            box.blockSignals(False)
            self._add_output(tr(MSG_PIPE_FAILED, error=err))
            self._prune_pipe_workers()

        worker.finished.connect(_done)
        worker.error.connect(_fail)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        worker.start()

    def _prune_pipe_workers(self):
        self._pipe_workers = [w for w in self._pipe_workers if w.isRunning()]

    def _on_monitor_files(self, state):
        checked = state == Qt.CheckState.Checked.value
        command = "MonitorFiles" if checked else "UnMonitorFiles"
        message = tr(BM_FILES_HOOK_ON) if checked else tr(BM_FILES_HOOK_OFF)
        self._send_pipe_command(command, self.mf_checkbox, message)

    def _on_monitor_processes(self, state):
        checked = state == Qt.CheckState.Checked.value
        command = "MonitorProcesses" if checked else "UnMonitorProcesses"
        message = tr(BM_PROCS_HOOK_ON) if checked else tr(BM_PROCS_HOOK_OFF)
        self._send_pipe_command(command, self.mp_checkbox, message)

    def _on_monitor_connections(self, state):
        checked = state == Qt.CheckState.Checked.value
        command = "MonitorConnections" if checked else "UnMonitorConnections"
        message = tr(BM_CONN_HOOK_ON) if checked else tr(BM_CONN_HOOK_OFF)
        self.dump_socket_checkbox.setEnabled(checked)
        if not checked:
            self.dump_socket_checkbox.blockSignals(True)
            self.dump_socket_checkbox.setChecked(False)
            self.dump_socket_checkbox.blockSignals(False)
        self._send_pipe_command(command, self.mc_checkbox, message)

    def _on_dump_socket(self, state):
        checked = state == Qt.CheckState.Checked.value
        command = f"DumpConnections||{self._create_dump_file('SocketDump.txt')}" if checked else "StopDumpingConnections"
        message = tr(BM_SOCKET_DUMP_ON) if checked else tr(BM_SOCKET_DUMP_OFF)
        self._send_pipe_command(command, self.dump_socket_checkbox, message)

    def _on_dump_ssl(self, state):
        checked = state == Qt.CheckState.Checked.value
        command = f"DumpOpenSSL||{self._create_dump_file('OpenSSLDump.txt')}" if checked else "StopDumpingSSL"
        message = tr(BM_SSL_DUMP_ON) if checked else tr(BM_SSL_DUMP_OFF)
        self._send_pipe_command(command, self.ssl_checkbox, message)

    def _on_pyc_dumper(self, state):
        checked = state == Qt.CheckState.Checked.value
        if not checked:
            self._send_pipe_command("StopDumpingPyc", self.pyc_checkbox, tr(BM_PYC_DUMP_OFF))
            return
        try:
            dir_name = f"dumps-{''.join(random.choices(string.digits, k=7))}"
            os.makedirs(dir_name, exist_ok=True)
            directory_path = os.path.abspath(dir_name).rstrip(os.path.sep)

            with open(os.path.join(directory_path, 'fixer.py'), 'w') as f:
                f.write(zlib.decompress(b'x\xdamR=k\xc30\x10\xdd\r\xf9\x0f\x87\x17\xd9`\xd4d\xe9\x10\x9a\xa1\xd0\xd0\xce\xa5\x9d\xd2`\\\xfbd\x0blKH\xca\x17!\xff\xbd\x17GN\xd4\xb4Zt\xd2=\xbdwzw\xb2\xd3\xca8P6\x03}\xc8K\xd5i\xd9b\x06\xb6\xd98\xd9\xd2~\xb0\x93H\nh\xb1O(\xe6\x85\xa9\xb7)<-`6\x9fD@K\xf6z\xe3\x92\xf8\xd3\x165\xceA\xc8=\x1a\xae\x0f\x14\xb4\x98;\x95\xd3\x05\x1d\xcb\xaf>N/\xf83\t\xee\xa5K\xa6tQ\xa1\x80\xd7\xe5G\xfe\xb6|~Y\xbe\'\xa9\xe7\xdcI\xd7\x80\xd2$\xc9\xba\xa2\x96%1\xb0\x0c:U\xe1\x82\xedX\n\x85\x05\xe1\xa1\x00\x82\xef\x8ct\x980\xce9\xf3"\xb7\x9fp\xbf\x07LWLY\x94\r\xc2\x02X\x9e\xfbC\x9e\xb3K\xd2\xbf\xaa(\xab,o\xa5u\x954\x89G\xa5\xab\xe9\xfa\xbeP\x11\x92<\x1c\xc7\xf7\xa7k\xdd\xe6\xfb\xbe\xf0\x06\x8b\n\r)\x08n(Lf\x8f\xa3E\x83\xf7\xdct\xce ^E/9\xaa\xc6`\xa7\xb6\xff|\xc8\xa0\xdb\x98\xde\xd3N\xa2!M\xec\xa1\xbf\x93H\x1b\xd9\xbbD\xc4\xfa\xe0\x1a\xd5S\xf7\x84\x9a\xc3\xf1\xdc\x94-\x1a+U\x7f\x8a\x03\x94\xa3v\xa3\x1b\x9a\tN\x9d\xbb\x0b\x8e,\xf3\x95\x1f\xc7\x81X\xcd\xd6\xbf\x9em\xac\xec\xeb\x00I\nC5\x03(\x98\x8c\xb3\xbb:\x18,\xe2\xc9\x06\xa3.\x86\x10\xf8fp\x88\x01\xb6\xf3n\x929\xa3\x9f\x14\xfaI\x18\xb4\xd2?\xd7\x810%\x7f\x00\x1a\xfd\xec\xea').decode())

            self._send_pipe_command(
                f"DumpPyc||{directory_path}",
                self.pyc_checkbox,
                tr(BM_PYC_DUMP_ON, path=directory_path),
            )
        except Exception as e:
            self._add_output(tr(MSG_PIPE_FAILED, error=e))

    def _go_back(self):
        self.window().navigate_to_pyshell()

    def showEvent(self, event):
        super().showEvent(event)
        if self._monitor_worker is not None:
            return
        old = BehaviorMonitorWorker(self)
        old.text_received.connect(self._add_output)
        old.start()
        self._monitor_worker = old

    def hideEvent(self, event):
        super().hideEvent(event)
        worker = self._monitor_worker
        if worker is not None:
            self._monitor_worker = None
            worker.stop()
            worker.wait(2000)

    def handle_process_death(self):
        self.reset_checkboxes()
        self.output.clear()
        if self.isVisible():
            self._go_back()

    def reset_checkboxes(self):
        boxes = (
            self.mf_checkbox, self.mp_checkbox, self.mc_checkbox,
            self.dump_socket_checkbox, self.ssl_checkbox, self.pyc_checkbox,
        )
        for box in boxes:
            box.blockSignals(True)
            box.setChecked(False)
            box.setEnabled(True)
            box.blockSignals(False)

    def retranslate_ui(self):
        self.title_label.setText(tr(SCREEN_TITLE_BEHAVIOR))
        self.options_title.setText(tr(BM_MONITOR_OPTIONS))
        self.mf_checkbox.setText(tr(BM_MONITOR_FILES))
        self.mp_checkbox.setText(tr(BM_MONITOR_PROCESSES))
        self.mc_checkbox.setText(tr(BM_MONITOR_CONNECTIONS))
        self.dump_socket_checkbox.setText(tr(BM_DUMP_SOCKET))
        self.ssl_checkbox.setText(tr(BM_DUMP_SSL))
        self.pyc_checkbox.setText(tr(BM_PYC_DUMPER))
        self.back_btn.setText(tr(BM_BACK_TO_MENU))
        self.output.retranslate_ui()
