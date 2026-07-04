# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import json
import platform
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QTextBrowser, QScroller
)
from PySide6.QtCore import Qt, QTimer

from de4py.ui.workers.changelog_worker import ChangelogWorker
from de4py.lang import tr
from de4py.lang.keys import (
    SCREEN_TITLE_HOME, HOME_CHANGELOG_TITLE, HOME_ENV_INFO,
    HOME_PYTHON_VERSION, HOME_ARCH, HOME_OS,
)

_PYTHON_VERSION = platform.python_version()
_ARCH = platform.architecture()[0]
_UNAME = platform.uname()
_OS_STR = f"{_UNAME.system} {_UNAME.release}"



class HomeScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._setup_clock()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(20)



        self.title_label = QLabel(tr(SCREEN_TITLE_HOME))
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(40)

        self.changelog_frame = self._create_changelog_frame()
        content_layout.addWidget(self.changelog_frame)

        right_layout = QVBoxLayout()
        right_layout.setSpacing(20)

        env_frame = self._create_env_frame()
        right_layout.addWidget(env_frame)

        self.clock_frame = self._create_clock_frame()
        right_layout.addWidget(self.clock_frame)

        right_layout.addStretch()
        content_layout.addLayout(right_layout)
        content_layout.addStretch()

        layout.addLayout(content_layout, 1)
        self.changelog_area.setObjectName("ChangelogArea")
        self.changelog_content.setObjectName("ChangelogContent")
        self.clock_frame.setObjectName("ClockFrame")

    def _create_changelog_frame(self):
        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame.setMinimumWidth(360)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.changelog_title = QLabel(tr(HOME_CHANGELOG_TITLE))
        self.changelog_title.setObjectName("ChangelogTitleLabel")
        layout.addWidget(self.changelog_title)

        self.changelog_area = QScrollArea()
        self.changelog_area.setWidgetResizable(True)
        self.changelog_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.changelog_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        QScroller.grabGesture(self.changelog_area.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)

        self.changelog_content = QTextBrowser()
        self.changelog_content.setHtml("Loading...")
        self.changelog_content.setOpenExternalLinks(True)
        self.changelog_area.setWidget(self.changelog_content)

        layout.addWidget(self.changelog_area)

        return frame

    def _create_env_frame(self):
        self.env_frame = QFrame()
        self.env_frame.setObjectName("StyledFrame")
        layout = QVBoxLayout(self.env_frame)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        self.env_title = QLabel(tr(HOME_ENV_INFO))
        self.env_title.setObjectName("EnvTitleLabel")
        layout.addWidget(self.env_title)

        self.python_version_label = QLabel()
        self.python_version_label.setObjectName("EnvLabel")
        layout.addWidget(self.python_version_label)

        self.arch_label = QLabel()
        self.arch_label.setObjectName("EnvLabel")
        layout.addWidget(self.arch_label)

        self.os_label = QLabel()
        self.os_label.setObjectName("EnvLabel")
        layout.addWidget(self.os_label)

        self._update_env_info()

        layout.addStretch()
        return self.env_frame

    def _update_env_info(self):
        self.python_version_label.setText(f"<b>{tr(HOME_PYTHON_VERSION)}:</b> {_PYTHON_VERSION}")
        self.arch_label.setText(f"<b>{tr(HOME_ARCH)}:</b> {_ARCH}")
        self.os_label.setText(f"<b>{tr(HOME_OS)}:</b> {_OS_STR}")

    def retranslate_ui(self):
        self.title_label.setText(tr(SCREEN_TITLE_HOME))
        self.changelog_title.setText(tr(HOME_CHANGELOG_TITLE))
        self.env_title.setText(tr(HOME_ENV_INFO))
        self._update_env_info()

    def _create_clock_frame(self):
        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame.setFixedWidth(300)

        layout = QVBoxLayout(frame)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.clock_label = QLabel("00:00:00")
        self.clock_label.setObjectName("ClockLabel")
        layout.addWidget(self.clock_label)

        return frame

    def _setup_clock(self):
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

    def _update_clock(self):
        now = datetime.now()
        self.clock_label.setText(now.strftime("%H:%M:%S"))

    def _load_data(self):
        self._changelog_worker = ChangelogWorker(self)
        self._changelog_worker.finished.connect(self._on_changelog_loaded)
        self._changelog_worker.error.connect(self._on_changelog_error)
        self._changelog_worker.start()

    def _on_changelog_loaded(self, data: str):
        try:
            changelog_data = json.loads(data)
            changelog_data.reverse()
            parts = []
            for version in changelog_data:
                parts.append(f"<h3>Version {version['version']}</h3><ul>")
                for change in version.get('changes', []):
                    parts.append(f"<li>{change}</li>")
                parts.append("</ul>")
            self.changelog_content.setText("".join(parts))
        except Exception:
            self.changelog_content.setText(data)

    def _on_changelog_error(self, error: str):
        self.changelog_content.setText(error)
