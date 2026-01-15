# screenshot:
# https://prnt.sc/-gQk1pG6AIDl

from plugins import ThemePlugin

class HackerTheme(ThemePlugin):
    def __init__(self):
        super().__init__()
        self.name = "hacker theme"
        self.creator = "Fadi002"
        self.link = "https://github.com/Fadi002/de4py-plugins-repo/blob/main/themes/hackertheme.py"
        self.qss = """
QMainWindow,QWidget#CentralWidget,QWidget#MainContent {
background-color:#000000
}

QWidget {
background-color:transparent;
color:#ffffffaa;
outline:none;
font-family:"Share Tech Mono",monospace
}

QFrame#StyledFrame,QFrame#PluginCard {
background-color:#1f1f1f;
border:2px solid #00ff22;
border-radius:14px;
padding:20px
}

QFrame#ClockFrame {
background-color:#1f1f1f;
border:1px solid rgba(0,255,0,0.5);
border-radius:14px;
padding:20px
}

QWidget#Sidebar {
background-color:rgba(0,255,0,0.1);
border:none;
qproperty-glow_color:#00ff22
}

QFrame#SidebarRightLine {
background-color:rgba(0,255,0,0.8);
border:none
}

QLabel#SidebarTitle {
color:#00ff22;
font-size:24px;
font-weight:800;
letter-spacing:2px;
margin-bottom:5px;
text-transform:uppercase
}

QFrame#SidebarLine {
background-color:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 transparent,stop:0.5 rgba(0,255,0,0.8),stop:1 transparent);
max-height:2px;
margin-bottom:10px
}

QWidget#LoadingOverlay,QWidget#ModalOverlay {
background-color:rgba(0,0,0,160)
}

QFrame#NotificationFrame {
qproperty-borderColor:#00ff22;
qproperty-borderWidth:2;
border-radius:14px;
background:transparent
}

QPushButton {
background-color:rgba(0,255,0,0.1);
color:#00ff22;
border:1px solid #00ff22;
border-radius:8px;
padding:6px 12px;
font-size:14px;
font-weight:500
}

QPushButton:hover {
background-color:rgba(0,255,0,0.2);
color:#00ff22
}

QPushButton:pressed {
background-color:rgba(0,255,34,0.4)
}

QPushButton:disabled {
background-color:rgba(51,51,51,0.7);
color:#777777
}

QPushButton#NavButton {
background-color:transparent;
color:#8b949e;
text-align:left;
padding:12px 20px;
border-radius:8px;
margin:4px 10px;
font-size:14px;
font-weight:500;
qproperty-shadow_active_color:transparent
}

QPushButton#NavButton:hover {
background-color:rgba(255,255,255,0.05);
color:#ffffff
}

QPushButton#NavButton[active="true"] {
background-color:rgba(0,255,0,0.15);
color:#00ff22;
border-left:3px solid #00ff22;
border-radius:8px
}

QPushButton#HamburgerButton {
background-color:rgba(100,100,100,0.1);
color:#00ff22;
border-radius:25px;
font-size:24px;
padding:0;
min-width:50px;
min-height:50px
}

QPushButton#HamburgerButton:hover {
background-color:rgba(120,120,120,0.2)
}

QLineEdit {
background-color:#1f1f1f;
color:#ffffff;
border:1px solid rgba(0,255,0,0.3);
border-radius:8px;
padding:8px 12px;
selection-background-color:#00ff22;
min-height:28px
}

QLineEdit:hover {
background-color:#1a1a1a;
border:1px solid rgba(0,255,34,0.5)
}

QLineEdit:focus {
background-color:#000000;
border:1px solid #00ff22
}

QTextEdit,QPlainTextEdit {
background-color:#000000;
color:#ffffffaa;
border:1px solid rgba(0,255,0,0.2);
border-radius:8px;
padding:12px;
font-family:"Share Tech Mono",monospace;
font-size:13px;
selection-background-color:#00ff22;
selection-color:#000000
}

QTextEdit:focus,QPlainTextEdit:focus {
border:1px solid rgba(0,255,34,0.5);
background-color:#000000
}

QLabel#OutputTitle {
font-size:20px;
color:#00ff22;
letter-spacing:1.2px;
margin-bottom:4px;
text-transform:uppercase
}

QLabel#EnvTitleLabel {
font-size:20px;
color:#00ff22;
letter-spacing:.8px;
margin-bottom:6px
}

QLabel#EnvLabel {
font-size:14px;
color:#e1e1e1;
padding:2px 0
}

QScrollBar:vertical {
background:transparent;
width:6px;
margin:0
}

QScrollBar::handle:vertical {
background:rgba(0,255,0,0.4);
min-height:20px;
border-radius:3px
}

QScrollBar::handle:vertical:hover {
background:rgba(0,255,0,0.8)
}

QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {
height:0
}

QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {
background:none
}

QScrollArea {
background-color:transparent;
border:none
}

QScrollArea#ChangelogArea QScrollBar:vertical {
width:4px
}

QCheckBox {
spacing:8px;
color:#ffffff;
background-color:transparent
}

QCheckBox::indicator {
width:18px;
height:18px;
border-radius:4px;
border:2px solid #00ff22;
background-color:rgba(34,34,34,0.85)
}

QCheckBox::indicator:checked {
background-color:#00ff22
}

QLabel {
background-color:transparent;
color:#ffffff
}

QLabel#TitleLabel {
font-size:26px;
font-weight:800;
color:#ffffff;
letter-spacing:.5px
}

QLabel#SubtitleLabel {
font-size:18px;
font-weight:600
}

QLabel#ClockLabel {
font-family:"Share Tech Mono",monospace;
font-size:50px;
font-weight:400;
color:#00ff22
}

QLabel#LinkLabel {
color:#00ff22;
text-decoration:underline
}

QScrollArea#ChangelogArea {
background-color:#000000;
border:1px solid rgba(0,255,34,0.3);
border-radius:10px
}

QTextBrowser#ChangelogContent {
background-color:#000000;
color:#e0e0e0;
font-size:14px;
line-height:1.6em;
padding:12px;
border-radius:8px
}

QLabel#ChangelogTitleLabel {
font-size:26px;
color:#00ff22;
margin-bottom:12px;
letter-spacing:1.2px;
text-transform:uppercase
}

QLabel#FilePathLabel {
color:#8b949e;
border:1px solid rgba(0,255,34,0.3);
border-radius:10px;
padding:8px;
font-family:"Consolas",monospace
}

QProgressBar {
border:none;
background-color:rgba(255,255,255,0.08);
border-radius:2px
}

QProgressBar::chunk {
background-color:#00ff22;
border-radius:2px
}

QFrame#ModeSelectorFrame {
background-color:#1f1f1f;
border:1.5px solid #00ff22;
border-radius:12px;
padding:0;
margin:0
}

QLabel#ModeLabel {
font-size:14px;
background:transparent;
padding:0;
margin:0
}

QLabel#ModeLabel[active="true"] {
color:#00ff22;
font-weight:bold
}

QLabel#ModeLabel[active="false"] {
color:#777777;
font-weight:normal
}

"""

def register():
    return HackerTheme()
