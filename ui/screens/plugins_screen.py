from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QScrollArea, QPushButton, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from plugins import plugins
from plugins.plugins import ThemePlugin
from ui.controllers import config_controller


class PluginsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(20)
        
        title = QLabel("PLUGINS")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
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
        
        if not config_controller.get_load_plugins():
            no_plugins_label = QLabel("Plugins are disabled")
            no_plugins_label.setObjectName("TitleLabel")
            no_plugins_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.plugins_layout.addWidget(no_plugins_label)
            return
        
        try:
            loaded_plugins = plugins.load_plugins()
            
            if not loaded_plugins:
                no_plugins_label = QLabel("No plugins were loaded")
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
            error_label = QLabel(f"Failed to load plugins: {str(e)}")
            self.plugins_layout.addWidget(error_label)

    def _create_plugin_card(self, plugin, plugin_type):
        frame = QFrame()
        frame.setObjectName("PluginCard")
        
        layout = QVBoxLayout(frame)
        
        name_label = QLabel(f'<a href="{plugin.link}" style="color: #0287CF;">{plugin.plugin_name}</a>')
        name_label.setOpenExternalLinks(True)
        name_label.setObjectName("SubtitleLabel")
        layout.addWidget(name_label)
        
        creator_label = QLabel(f"Made by: {plugin.creator}")
        layout.addWidget(creator_label)
        
        type_label = QLabel(f"Type: {plugin_type.capitalize()}")
        type_label.setStyleSheet("color: #888;")
        layout.addWidget(type_label)
        
        if plugin_type == "theme" and isinstance(plugin, ThemePlugin):
            apply_btn = QPushButton("Apply Theme")
            apply_btn.clicked.connect(lambda: self._apply_theme(plugin))
            layout.addWidget(apply_btn)
            
        return frame

    def _apply_theme(self, plugin):
        if hasattr(plugin, 'qss'):
            QApplication.instance().setStyleSheet(plugin.qss)
