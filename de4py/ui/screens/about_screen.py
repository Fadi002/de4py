from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt


class AboutScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame.setFixedSize(350, 220)
        
        frame_layout = QVBoxLayout(frame)
        frame_layout.setSpacing(12)
        frame_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title = QLabel("ABOUT")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(title)
        
        github1 = QLabel('GitHub: <a href="https://github.com/fadi002" style="color: #0287CF;">fadi002</a>')
        github1.setOpenExternalLinks(True)
        github1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(github1)
        
        github2 = QLabel('GitHub: <a href="https://github.com/AdvDebug" style="color: #0287CF;">AdvDebug</a>')
        github2.setOpenExternalLinks(True)
        github2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(github2)

        matrix = QLabel('<a href="https://matrix.to/#/#de4py:matrix.org" style="color: #0287CF;">Matrix Community</a>')
        matrix.setOpenExternalLinks(True)
        matrix.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(matrix)
        
        discord = QLabel("Made by 0xmrpepe & advdebug with <3")
        discord.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(discord)
        
        layout.addWidget(frame)
