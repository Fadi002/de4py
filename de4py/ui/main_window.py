import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QPushButton
)
from de4py.ui.widgets.core_animations import AnimatedStackedWidget
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtGui import QIcon

from de4py.config.config import settings
from de4py.lang import translation_manager
from de4py.ui.motion.manager import MotionManager
from de4py.ui.widgets.hamburger_button import HamburgerButton
from de4py.ui.constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE,
    SIDEBAR_WIDTH, HAMBURGER_SIZE, SPACING_MD,
    SCREEN_HOME, SCREEN_DEOBFUSCATOR, SCREEN_PYSHELL, SCREEN_BEHAVIOR_MONITOR,
    SCREEN_ANALYZER, SCREEN_PLUGINS, SCREEN_SETTINGS, SCREEN_ABOUT,
    SCREEN_PYLINGUAL
)
from de4py.ui.navigation.sidebar import Sidebar
from de4py.ui.screens.home_screen import HomeScreen
from de4py.ui.screens.deobfuscator_screen import DeobfuscatorScreen
from de4py.ui.screens.pyshell_screen import PyShellScreen
from de4py.ui.screens.behavior_monitor_screen import BehaviorMonitorScreen
from de4py.ui.screens.analyzer_screen import AnalyzerScreen
from de4py.ui.screens.plugins_screen import PluginsScreen
from de4py.ui.screens.settings_screen import SettingsScreen
from de4py.ui.screens.about_screen import AboutScreen
from de4py.ui.screens.pylingual_screen import PyLingualScreen
from de4py.ui.widgets.notification_widget import NotificationManager
from de4py.ui.widgets.loading_overlay import LoadingOverlay
from de4py.ui.widgets.custom_title_bar import CustomTitleBar

TRANSPARENT_STYLESHEET = """
/* Transparency Overrides */
QMainWindow, QWidget#CentralWidget {
    background-color: rgba(20, 20, 20, 0.02); /* Near-zero alpha to force render surface */
}
QWidget#MainContent {
    background-color: transparent;
}
QWidget#Sidebar {
    background-color: rgba(20, 30, 48, 0.75);
    border-right: 1px solid rgba(88, 166, 255, 0.2);
}
QPushButton#NavButton {
    color: #ffffff;
    font-weight: 500;
}
QScrollArea#ChangelogArea, QScrollArea#ChangelogArea > QWidget > QWidget {
    background: transparent;
    border: none;
}
QTextBrowser#ChangelogContent {
    background-color: transparent;
    border: none;
    color: #e6edf3;
}
QFrame#StyledFrame, QFrame#PluginCard, QFrame#ClockFrame {
    background-color: rgba(24, 28, 36, 0.40);
}
QFrame#ModeSelectorFrame {
    background-color: rgba(24, 28, 36, 0.40);
}
QFrame#NotificationFrame {
    qproperty-overlayColorName: rgba(25, 25, 25, 0.40);
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background-color: rgba(24, 28, 36, 0.5);
}
/* Ensure these input widgets become more opaque on focus/hover for readability */
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    background-color: rgba(30, 36, 46, 0.9);
}
"""

class MainWindow(QMainWindow):
    """
    The main application window for de4py.
    Manages the sidebar navigation, the screen stack, and provides unified
    access to global overlays like notifications and loading screens.
    """
    def __init__(self, title=None):
        super().__init__()
        from de4py.lang import tr, keys
        self.setWindowTitle(title if title else tr(keys.APP_NAME))
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self._sidebar_visible = False
        
        translation_manager.load_language(settings.language)
        
        self._setup_ui()
        self._connect_signals()
        
        translation_manager.language_changed.connect(self._on_language_changed)

        if settings.transparent_ui:
            self.set_transparent_ui(True)

    def set_transparent_ui(self, enabled: bool):
        try:
            from de4py.utils.win32_blur import enable_dynamic_blur, disable_blur
            
            # Toggling TranslucentBackground usually requires a hide/show cycle
            was_visible = self.isVisible()
            if was_visible:
                self.hide()

            if enabled:
                theme_colors = {}
                active_style = TRANSPARENT_STYLESHEET
                
                if settings.active_theme:
                    try:
                        from plugins import load_plugins
                        loaded = load_plugins()
                        active_name = settings.active_theme.strip().lower()
                        for p in loaded:
                            inst = p.get("instance")
                            if inst and inst.name.strip().lower() == active_name:
                                if hasattr(inst, "colors") and inst.colors:
                                    theme_colors = inst.colors
                                
                                if hasattr(inst, "transparent_qss") and inst.transparent_qss:
                                    active_style = inst.transparent_qss
                                break
                    except Exception:
                        pass
                
                enable_dynamic_blur(self, theme_colors)
                self.setStyleSheet(active_style)
                self.title_bar.set_theme_colors(theme_colors)
                self.title_bar.show()
                self.title_bar.raise_()
            else:
                disable_blur(self)
                self.setStyleSheet("")
                self.title_bar.hide()
            
            if was_visible:
                self.show()
                
        except Exception:
            self.show() # Safety fallback

    def nativeEvent(self, eventType, message):
        """Handle Windows system color change events to refresh blur."""
        try:
            if eventType == "windows_generic_MSG":
                import ctypes.wintypes
                msg = ctypes.wintypes.MSG.from_address(message.__int__())
                if msg.message in (0x0320, 0x001A):
                    if settings.transparent_ui:
                        self.set_transparent_ui(True) 
        except Exception:
            pass
        return super().nativeEvent(eventType, message)

    def _setup_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.title_bar = CustomTitleBar(self)
        self.title_bar.hide()
        
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
        
        self._setup_notification_manager()
        self._setup_loading_overlay()
        
        # Determine icon path safely
        base_path = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_path, "resources", "menu.svg")
        
        self.hamburger_btn = HamburgerButton(content_widget)
        self.hamburger_btn.setObjectName("HamburgerButton")
        self.hamburger_btn.move(SPACING_MD, SPACING_MD)
        if os.path.exists(icon_path):
             self.hamburger_btn.setIcon(QIcon(icon_path))
        
        # Initial raise
        self.hamburger_btn.raise_()
        self.title_bar.raise_()
        
        self.sidebar.setFixedWidth(0) # Ensure start state
    

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

    def _setup_notification_manager(self):
        self.notification_manager = NotificationManager(self)

    def _setup_loading_overlay(self):
        self.loading_overlay = LoadingOverlay(self)
        self.loading_overlay.hide()

    def _connect_signals(self):
        self.hamburger_btn.clicked.connect(self._toggle_sidebar)
        self.sidebar.navigation_requested.connect(self._navigate_to)
        
        # Custom Title Bar Signals
        self.title_bar.close_requested.connect(self.close)
        self.title_bar.minimize_requested.connect(self.showMinimized)
        
        # Connect process death from PyShell to Behavior Monitor reset
        self.pyshell_screen.process_died.connect(self.behavior_monitor_screen.handle_process_death)

    def _toggle_sidebar(self):
        start_width = self.sidebar.width()
        target_width = SIDEBAR_WIDTH if not self._sidebar_visible else 0
        
        # Use MotionManager's specialized helper for "fixedWidth" animation inertia
        MotionManager.animate_sidebar_width(
            target=self.sidebar,
            start=start_width,
            end=target_width,
            duration=MotionManager.DURATION_SLIDE,
            easing=MotionManager.EASE_HEAVY
        )

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
            from de4py.utils import sentry
            sentry.breadcrumb(f"Navigating to screen: {screen_id}", category="navigation")
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
        self._update_title_bar_geometry()

    def _update_title_bar_geometry(self):
        if hasattr(self, 'title_bar'):
            self.title_bar.setGeometry(0, 0, self.width(), 28)
            self.title_bar.raise_()

    def _on_language_changed(self, lang_code: str):
        """
        Handle runtime language changes.
        Propagates the change to all screens and widgets that support retranslation.
        """
        from de4py.lang import tr, keys
        self.setWindowTitle(tr(keys.APP_NAME))
        
        # Retranslate sidebar
        if hasattr(self.sidebar, 'retranslate_ui'):
            self.sidebar.retranslate_ui()

        
        # Retranslate all screens in the stack
        for i in range(self.screen_stack.count()):
            widget = self.screen_stack.widget(i)
            if hasattr(widget, 'retranslate_ui'):
                widget.retranslate_ui()
        
        # Show notification about language change
        from de4py.lang import tr, keys
        available = translation_manager.get_available_languages()
        lang_name = available.get(lang_code, lang_code)
        self.show_notification("info", tr(keys.NOTIF_LANGUAGE_CHANGED, language=lang_name))
