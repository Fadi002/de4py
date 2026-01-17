from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QScrollArea, QPushButton, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from de4py.config.config import settings
import plugins
from plugins import ThemePlugin
from de4py.lang import tr
from de4py.lang.keys import (
    SCREEN_TITLE_PLUGINS, PLUGINS_DISABLED, PLUGINS_NONE_LOADED,
    PLUGINS_FAILED_LOAD, PLUGINS_MADE_BY, PLUGINS_TYPE,
    PLUGINS_APPLY, PLUGINS_RESET, PLUGINS_THEME_APPLIED, PLUGINS_THEME_FAILED, PLUGINS_THEME_RESET,
    MSG_SUCCESS, MSG_ERROR, MSG_INFO, MSG_WARNING
)



class PluginsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(20)
        
        self.title_label = QLabel(tr(SCREEN_TITLE_PLUGINS))
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.plugins_container = QWidget()
        self.plugins_layout = QVBoxLayout(self.plugins_container)
        self.plugins_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.plugins_layout.setSpacing(10)
        
        scroll_area.setWidget(self.plugins_container)
        layout.addWidget(scroll_area, 1)

    def showEvent(self, event):
        super().showEvent(event)
        self._load_plugins()

    def _load_plugins(self):
        while self.plugins_layout.count():
            child = self.plugins_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not settings.load_plugins:
            no_plugins_label = QLabel(tr(PLUGINS_DISABLED))
            no_plugins_label.setObjectName("TitleLabel")
            no_plugins_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.plugins_layout.addWidget(no_plugins_label)
            return
        
        try:
            loaded_plugins = plugins.load_plugins()
            
            if not loaded_plugins:
                no_plugins_label = QLabel(tr(PLUGINS_NONE_LOADED))
                no_plugins_label.setObjectName("TitleLabel")
                no_plugins_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.plugins_layout.addWidget(no_plugins_label)
                return
            
            for plugin_data in loaded_plugins:
                plugin_instance = plugin_data.get("instance")
                plugin_type = plugin_data.get("type")
                
                if plugin_instance:
                    card = self._create_plugin_card(plugin_instance, plugin_type)
                    self.plugins_layout.addWidget(card)
        except Exception as e:
            error_label = QLabel(f"{tr(PLUGINS_FAILED_LOAD)}: {str(e)}")
            self.plugins_layout.addWidget(error_label)

    def _create_plugin_card(self, plugin, plugin_type):
        frame = QFrame()
        frame.setObjectName("PluginCard")
        
        layout = QVBoxLayout(frame)
        
        name_label = QLabel(f'<a href="{plugin.link}" style="color: #0287CF;">{plugin.name}</a>')
        name_label.setOpenExternalLinks(True)
        name_label.setObjectName("SubtitleLabel")
        layout.addWidget(name_label)
        
        creator_label = QLabel(f"{tr(PLUGINS_MADE_BY)} {plugin.creator}")
        layout.addWidget(creator_label)
        
        type_label = QLabel(f"{tr(PLUGINS_TYPE)} {plugin_type.capitalize()}")
        type_label.setStyleSheet("color: #888;")
        layout.addWidget(type_label)
        
        if plugin_type == "theme" and isinstance(plugin, ThemePlugin):
            is_active = (settings.active_theme == plugin.name)
            btn_text = tr(PLUGINS_RESET) if is_active else tr(PLUGINS_APPLY)
            apply_btn = QPushButton(btn_text)
            apply_btn.clicked.connect(lambda: self._apply_theme(plugin))
            layout.addWidget(apply_btn)
            
        return frame

    def _apply_theme(self, plugin):
        if settings.active_theme == plugin.name:
            self._reset_theme()
            return

        try:
            if hasattr(plugin, 'qss'):
                QApplication.instance().setStyleSheet(plugin.qss)
                settings.active_theme = plugin.name
                settings.save()
                self.window().show_notification("success", tr(PLUGINS_THEME_APPLIED, theme=plugin.name))
                self._load_plugins() 
            else:
                raise ValueError("Plugin missing QSS data")
        except Exception as e:
            from de4py import main
            QApplication.instance().setStyleSheet(main.DEFAULT_QSS)
            settings.active_theme = None
            settings.save()
            self.window().show_notification("failure", tr(PLUGINS_THEME_FAILED, theme=plugin.name))
            self._load_plugins()

    def _reset_theme(self):
        from de4py import main
        QApplication.instance().setStyleSheet(main.DEFAULT_QSS)
        settings.active_theme = None
        settings.save()
        self.window().show_notification("success", tr(PLUGINS_THEME_RESET))
        self._load_plugins()

    def retranslate_ui(self):
        """Update UI texts when language changes."""
        self.title_label.setText(tr(SCREEN_TITLE_PLUGINS))
        # Plugin cards are dynamic, so we just reload everything
        self._load_plugins()
