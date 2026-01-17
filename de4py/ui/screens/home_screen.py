import json
import platform
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QTextBrowser
)
from PySide6.QtCore import Qt, QTimer

from de4py.ui.widgets.output_textarea import OutputTextArea
from de4py.ui.workers.changelog_worker import ChangelogWorker
from de4py.lang import tr
from de4py.lang.keys import (
    SCREEN_TITLE_HOME, HOME_CHANGELOG_TITLE, HOME_ENV_INFO,
    HOME_PYTHON_VERSION, HOME_ARCH, HOME_OS
)



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

        self.changelog_title = QLabel(tr(HOME_CHANGELOG_TITLE))
        self.changelog_title.setObjectName("ChangelogTitleLabel")
        layout.addWidget(self.changelog_title)

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

        self.env_title = QLabel(tr(HOME_ENV_INFO))
        self.env_title.setObjectName("EnvTitleLabel")
        layout.addWidget(self.env_title)

        self.pv_label = QLabel()
        self.pv_label.setObjectName("EnvLabel")
        layout.addWidget(self.pv_label)

        self.arch_label = QLabel()
        self.arch_label.setObjectName("EnvLabel")
        layout.addWidget(self.arch_label)

        system_info = platform.uname()
        self.os_label = QLabel()
        self.os_label.setObjectName("EnvLabel")
        layout.addWidget(self.os_label)
        
        self._update_env_info()

        layout.addStretch()
        return self.env_frame

    def _update_env_info(self):
        self.pv_label.setText(f"<b>{tr(HOME_PYTHON_VERSION)}:</b> {platform.python_version()}")
        self.arch_label.setText(f"<b>{tr(HOME_ARCH)}:</b> {platform.architecture()[0]}")
        system_info = platform.uname()
        self.os_label.setText(f"<b>{tr(HOME_OS)}:</b> {system_info.system} {system_info.release}")

    def retranslate_ui(self):
        """Update UI texts when language changes."""
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
