import json
import platform
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QTextBrowser
)
from PySide6.QtCore import Qt, QTimer

from de4py.ui.widgets.output_textarea import OutputTextArea
from de4py.ui.workers.changelog_worker import ChangelogWorker



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

        
        title = QLabel("HOME")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        content_layout = QHBoxLayout()
        content_layout.setSpacing(40)
        
        self.changelog_frame = self._create_changelog_frame()
        content_layout.addWidget(self.changelog_frame)
        
        right_layout = QVBoxLayout()
        right_layout.setSpacing(20)
        
        self.env_frame = self._create_env_frame()
        right_layout.addWidget(self.env_frame)
        
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

        title_label = QLabel("CHANGE LOG")
        title_label.setObjectName("ChangelogTitleLabel")
        layout.addWidget(title_label)

        self.changelog_area = QScrollArea()
        self.changelog_area.setWidgetResizable(True)
        self.changelog_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.changelog_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Enable smooth scrolling
        from PySide6.QtWidgets import QScroller
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

        title_label = QLabel("Environment info")
        title_label.setObjectName("EnvTitleLabel")
        layout.addWidget(title_label)

        self.pv_label = QLabel(f"<b>Python version:</b> {platform.python_version()}")
        self.pv_label.setObjectName("EnvLabel")
        layout.addWidget(self.pv_label)

        self.arch_label = QLabel(f"<b>Arch:</b> {platform.architecture()[0]}")
        self.arch_label.setObjectName("EnvLabel")
        layout.addWidget(self.arch_label)

        system_info = platform.uname()
        self.os_label = QLabel(f"<b>OS:</b> {system_info.system} {system_info.release}")
        self.os_label.setObjectName("EnvLabel")
        layout.addWidget(self.os_label)

        layout.addStretch()
        return self.env_frame

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
        from datetime import datetime
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
            html = ""
            for version in changelog_data:
                html += f"<h3>Version {version['version']}</h3><ul>"
                for change in version.get('changes', []):
                    html += f"<li>{change}</li>"
                html += "</ul>"
            self.changelog_content.setText(html)
        except Exception:
            self.changelog_content.setText(data)

    def _on_changelog_error(self, error: str):
        self.changelog_content.setText(error)
