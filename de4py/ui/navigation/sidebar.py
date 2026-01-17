import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSpacerItem, QSizePolicy, QLabel, QFrame, QGraphicsDropShadowEffect
from PySide6.QtCore import Signal, QSize, Qt, Property
from PySide6.QtGui import QIcon, QColor

from de4py.lang import tr
from de4py.ui.constants import NAV_ITEMS, SIDEBAR_WIDTH, SPACING_SM
from de4py.ui.widgets.core_animations import AnimatedButton


class Sidebar(QWidget):
    navigation_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)
        self._active_id = "home"
        self._buttons = {}
        
        # Dedicated Glowing Right Border (to avoid affecting buttons)
        self.right_line = QFrame(self)
        self.right_line.setObjectName("SidebarRightLine")
        self.right_line.setFixedWidth(2)
        
        self.line_shadow = QGraphicsDropShadowEffect(self)
        self.line_shadow.setBlurRadius(20)
        self.line_shadow.setXOffset(5)
        self.line_shadow.setYOffset(0)
        self.line_shadow.setColor(QColor(88, 166, 255, 120)) # Stronger, focused glow
        self.right_line.setGraphicsEffect(self.line_shadow)

        # Title shadow (stored as attribute for dynamic updates)
        self.title_shadow = QGraphicsDropShadowEffect(self)
        self.title_shadow.setBlurRadius(15)
        self.title_shadow.setOffset(0, 0)
        self.title_shadow.setColor(QColor(88, 166, 255, 200)) # Stronger blue glow for text

        self._setup_ui()

    def get_glow_color(self):
        return self.line_shadow.color()

    def set_glow_color(self, color: QColor):
        self.line_shadow.setColor(QColor(color.red(), color.green(), color.blue(), 120))
        self.title_shadow.setColor(QColor(color.red(), color.green(), color.blue(), 200))

    glow_color = Property(QColor, get_glow_color, set_glow_color)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Keep the right line at the far right
        self.right_line.setGeometry(self.width() - 2, 0, 2, self.height())

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 20, 0, SPACING_SM)
        layout.setSpacing(0)

        # Branded Header
        from de4py.lang import keys
        self.title_label = QLabel(tr(keys.APP_NAME))
        self.title_label.setObjectName("SidebarTitle")

        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Add glow specifically to the title text
        self.title_label.setGraphicsEffect(self.title_shadow)
        
        layout.addWidget(self.title_label)

        # Separator Line (Horizontal)
        self.line = QFrame()
        self.line.setObjectName("SidebarLine")
        self.line.setFrameShape(QFrame.Shape.HLine)
        self.line.setFrameShadow(QFrame.Shadow.Plain)
        self.line.setFixedHeight(2)
        layout.addWidget(self.line)

        layout.addSpacing(15)
        
        base_path = os.path.dirname(os.path.abspath(__file__))
        resources_path = os.path.join(base_path, "..", "resources")
        
        for nav_id, label_key, icon_file in NAV_ITEMS:
            # Use translation key to get localized label
            btn = AnimatedButton(tr(label_key))
            btn.setObjectName("NavButton")
            btn.setProperty("nav_id", nav_id)
            btn.setMinimumHeight(45)
            # Cursor is handled by AnimatedButton
            
            icon_path = os.path.join(resources_path, icon_file)
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(24, 24))
            
            btn.clicked.connect(lambda checked, nid=nav_id: self._on_nav_click(nid))
            layout.addWidget(btn)
            self._buttons[nav_id] = btn
        
        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        
        self.set_active("home")

    def _on_nav_click(self, nav_id: str):
        self.navigation_requested.emit(nav_id)
        self.set_active(nav_id)

    def set_active(self, nav_id: str):
        self._active_id = nav_id
        for nid, btn in self._buttons.items():
            btn.setProperty("active", nid == nav_id)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def retranslate_ui(self):
        """
        Update all navigation button labels with current translations.
        Called when language changes at runtime.
        """
        for nav_id, label_key, icon_file in NAV_ITEMS:
            if nav_id in self._buttons:
                self._buttons[nav_id].setText(tr(label_key))

