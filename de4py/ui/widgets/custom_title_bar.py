from PySide6.QtWidgets import QWidget, QPushButton, QHBoxLayout
from PySide6.QtCore import Signal, Qt, QPoint

class CustomTitleBar(QWidget):
    minimize_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CustomTitleBar")
        self.setFixedHeight(28)

        self._dragging = False
        self._drag_pos = QPoint()

        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(1)

        # Minimize Button
        self.min_btn = QPushButton("—")
        self.min_btn.setObjectName("TitleBarMinButton")
        self.min_btn.setFixedSize(45, 28)
        self.min_btn.clicked.connect(self.minimize_requested.emit)
        layout.addWidget(self.min_btn)

        # Close Button
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("TitleBarCloseButton")
        self.close_btn.setFixedSize(45, 28)
        self.close_btn.clicked.connect(self.close_requested.emit)
        layout.addWidget(self.close_btn)

        self.setLayout(layout)


    def set_theme_colors(self, colors: dict):
        primary = colors.get("primary", "#ffffff")
        text = colors.get("text", "#ffffff")
        self.setStyleSheet(f"""
            QWidget#CustomTitleBar {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 rgba(0,0,0,0.08), stop:1 transparent);
            }}
            QPushButton {{
                background: transparent;
                border: none;
                color: {text};
                font-weight: bold;
                font-size: 14px;
                opacity: 0.5;
            }}
            QPushButton:hover {{
                background: rgba(255, 255, 255, 0.1);
                color: {primary};
                opacity: 1.0;
            }}
            QPushButton:pressed {{
                background: rgba(255, 255, 255, 0.05);
            }}
            QPushButton#TitleBarCloseButton:hover {{
                background: #e81123;
                color: white;
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        event.accept()