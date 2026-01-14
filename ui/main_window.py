import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QPushButton
)
from ui.widgets.core_animations import AnimatedStackedWidget
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtGui import QIcon

from ui.constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE,
    SIDEBAR_WIDTH, HAMBURGER_SIZE, SPACING_MD, ANIM_DURATION_NORMAL,
    SCREEN_HOME, SCREEN_DEOBFUSCATOR, SCREEN_PYSHELL, SCREEN_BEHAVIOR_MONITOR,
    SCREEN_ANALYZER, SCREEN_PLUGINS, SCREEN_SETTINGS, SCREEN_ABOUT,
    SCREEN_PYLINGUAL
)
from ui.navigation.sidebar import Sidebar
from ui.screens.home_screen import HomeScreen
from ui.screens.deobfuscator_screen import DeobfuscatorScreen
from ui.screens.pyshell_screen import PyShellScreen
from ui.screens.behavior_monitor_screen import BehaviorMonitorScreen
from ui.screens.analyzer_screen import AnalyzerScreen
from ui.screens.plugins_screen import PluginsScreen
from ui.screens.settings_screen import SettingsScreen
from ui.screens.about_screen import AboutScreen
from ui.screens.pylingual_screen import PyLingualScreen
from ui.widgets.notification_widget import NotificationManager
from ui.widgets.loading_overlay import LoadingOverlay


class MainWindow(QMainWindow):
    """
    The main application window for de4py.
    Manages the sidebar navigation, the screen stack, and provides unified
    access to global overlays like notifications and loading screens.
    """
    def __init__(self, title=None):
        super().__init__()
        self.setWindowTitle(title if title else WINDOW_TITLE)
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self._sidebar_visible = False
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.sidebar = Sidebar(self)
        self.sidebar.setFixedWidth(0)
        
        content_widget = QWidget()
        content_widget.setObjectName("MainContent")
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        self.screen_stack = AnimatedStackedWidget()
        self._create_screens()
        content_layout.addWidget(self.screen_stack)
        
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(content_widget, 1)
        
        self._create_hamburger_button(content_widget)
        self._setup_notification_manager()
        self._setup_loading_overlay()
        
        self._sidebar_anim = QPropertyAnimation(self.sidebar, b"minimumWidth")
        self._sidebar_anim.setDuration(ANIM_DURATION_NORMAL)
        self._sidebar_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

    def _create_screens(self):
        self.home_screen = HomeScreen(self)
        self.deobfuscator_screen = DeobfuscatorScreen(self)
        self.pyshell_screen = PyShellScreen(self)
        self.behavior_monitor_screen = BehaviorMonitorScreen(self)
        self.analyzer_screen = AnalyzerScreen(self)
        self.plugins_screen = PluginsScreen(self)
        self.settings_screen = SettingsScreen(self)
        self.about_screen = AboutScreen(self)
        self.pylingual_screen = PyLingualScreen(self)
        
        self.screen_stack.addWidget(self.home_screen)
        self.screen_stack.addWidget(self.deobfuscator_screen)
        self.screen_stack.addWidget(self.pyshell_screen)
        self.screen_stack.addWidget(self.behavior_monitor_screen)
        self.screen_stack.addWidget(self.analyzer_screen)
        self.screen_stack.addWidget(self.plugins_screen)
        self.screen_stack.addWidget(self.settings_screen)
        self.screen_stack.addWidget(self.about_screen)
        self.screen_stack.addWidget(self.pylingual_screen)
        
        self.screen_stack.setCurrentIndex(SCREEN_HOME)

    def _create_hamburger_button(self, parent):
        self.hamburger_btn = QPushButton("☰", parent)
        self.hamburger_btn.setObjectName("HamburgerButton")
        self.hamburger_btn.setFixedSize(HAMBURGER_SIZE, HAMBURGER_SIZE)
        self.hamburger_btn.move(SPACING_MD, SPACING_MD)
        self.hamburger_btn.raise_()
        
        base_path = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_path, "resources", "menu.svg")
        if os.path.exists(icon_path):
            self.hamburger_btn.setIcon(QIcon(icon_path))
            self.hamburger_btn.setIconSize(QSize(24, 24))
            self.hamburger_btn.setText("")

    def _setup_notification_manager(self):
        self.notification_manager = NotificationManager(self)

    def _setup_loading_overlay(self):
        self.loading_overlay = LoadingOverlay(self)
        self.loading_overlay.hide()

    def _connect_signals(self):
        self.hamburger_btn.clicked.connect(self._toggle_sidebar)
        self.sidebar.navigation_requested.connect(self._navigate_to)

    def _toggle_sidebar(self):
        target_width = SIDEBAR_WIDTH if not self._sidebar_visible else 0
        self._sidebar_anim.setStartValue(self.sidebar.width())
        self._sidebar_anim.setEndValue(target_width)
        self._sidebar_anim.start()
        self._sidebar_visible = not self._sidebar_visible

    def _navigate_to(self, screen_id: str):
        screen_map = {
            "home": SCREEN_HOME,
            "deobfuscator": SCREEN_DEOBFUSCATOR,
            "pyshell": SCREEN_PYSHELL,
            "analyzer": SCREEN_ANALYZER,
            "plugins": SCREEN_PLUGINS,
            "settings": SCREEN_SETTINGS,
            "about": SCREEN_ABOUT,
            "pylingual": SCREEN_PYLINGUAL,
        }
        if screen_id in screen_map:
            self.screen_stack.fade_to_index(screen_map[screen_id])
            self.sidebar.set_active(screen_id)
            
            # Auto-close sidebar after selection
            if self._sidebar_visible:
                self._toggle_sidebar()

    def navigate_to_behavior_monitor(self):
        self.screen_stack.fade_to_index(SCREEN_BEHAVIOR_MONITOR)

    def navigate_to_pyshell(self):
        self.screen_stack.fade_to_index(SCREEN_PYSHELL)
        self.sidebar.set_active("pyshell")

    def show_notification(self, notif_type: str, message: str):
        self.notification_manager.show_notification(notif_type, message)

    def show_loading(self):
        self.loading_overlay.fade_in()
        self.loading_overlay.raise_()

    def hide_loading(self):
        self.loading_overlay.fade_out()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.loading_overlay.setGeometry(self.rect())
