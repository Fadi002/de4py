from plugins import ThemePlugin

class CatppuccinLatte(ThemePlugin):
    def __init__(self):
        super().__init__()
        self.name = "Catppuccin Latte"
        self.description = "Light and airy theme, soft pastel accents, high readability."
        self.creator = "Fadi002"
        self.qss = """
QMainWindow,QWidget#CentralWidget,QWidget#MainContent
{
background-color:#EFF1F5
}

QWidget
{
background-color:transparent;
color:#4C4F69;
outline:none;
font-family:"Segoe UI","Inter","Tahoma","Arial","Microsoft YaHei","Malgun Gothic","SimSun",sans-serif
}

QFrame#StyledFrame,QFrame#PluginCard
{
background-color:rgba(239, 241, 245, 0.85);
border:1.5px solid #8839EF;
border-radius:14px;
padding:20px
}

QFrame#ClockFrame
{
background-color:rgba(239, 241, 245, 0.85);
border:1px solid rgba(136, 57, 239, 0.5);
border-radius:14px;
padding:20px
}

QWidget#Sidebar
{
background-color:rgba(239, 241, 245, 0.95);
border:none
}

QFrame#SidebarRightLine
{
background-color:rgba(30, 102, 245, 0.8);
border:none
}

QLabel#SidebarTitle
{
color:#1E66F5;
font-size:24px;
font-weight:800;
letter-spacing:2px;
margin-bottom:5px;
text-transform:uppercase
}

QFrame#SidebarLine
{
background-color:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 transparent,stop:0.5 rgba(30, 102, 245, 0.8),stop:1 transparent);
max-height:2px;
margin-bottom:10px
}

QWidget#LoadingOverlay,QWidget#ModalOverlay
{
background-color:rgba(0,0,0,160)
}

QFrame#NotificationFrame
{
qproperty-borderColor:#8839EF;
qproperty-borderWidth:1.5;
qproperty-overlayColorName:#D2FFFFFF;
qproperty-iconColorName:#ff4C4F69;
border-radius:14px;
background:transparent
}

QPushButton
{
background-color:#BCC0CC;
color:#4C4F69;
border:1px solid rgba(136, 57, 239, 0.3);
border-radius:8px;
padding:6px 12px;
font-size:14px;
font-weight:600
}

QPushButton:hover
{
background-color:rgba(136, 57, 239, 0.85);
color:#ffffff;
border:1px solid #8839EF
}

QPushButton:pressed
{
background-color:#8839EF
}

QPushButton:disabled
{
background-color:rgba(51,51,51,0.7);
color:#777777;
border:1px solid transparent
}

QPushButton#NavButton
{
background-color:transparent;
color:rgba(76, 79, 105, 0.6);
text-align:left;
padding:12px 20px;
border-radius:8px;
margin:4px 10px;
font-size:14px;
font-weight:500;
border:none;
qproperty-shadow_active_color:transparent;
qproperty-iconColorName:"#ff4C4F69"
}

QPushButton#NavButton:hover
{
background-color:rgba(76, 79, 105, 0.1);
color:#4C4F69
}

QPushButton#NavButton[active="true"]
{
background-color:rgba(136, 57, 239, 0.15);
color:#1E66F5;
border-left:3px solid #8839EF;
border-radius:3px 8px 8px 3px
}

QPushButton#HamburgerButton
{
background-color:rgba(76, 79, 105, 0.1);
color:#8839EF;
border-radius:25px;
font-size:24px;
padding:0;
min-width:50px;
min-height:50px;
border:none;
qproperty-iconColorName:"#8839EF"
}

QPushButton#HamburgerButton:hover
{
background-color:rgba(76, 79, 105, 0.2)
}

QLineEdit
{
background-color:rgba(239, 241, 245, 0.9);
color:#4C4F69;
border:1px solid rgba(136, 57, 239, 0.3);
border-radius:8px;
padding:8px 12px;
selection-background-color:#8839EF;
selection-color:#ffffff;
min-height:28px
}

QLineEdit:hover
{
background-color:rgba(239, 241, 245, 1.0);
border:1px solid rgba(136, 57, 239, 0.5)
}

QLineEdit:focus
{
background-color:#ffffff;
border:1px solid #8839EF
}

QTextEdit,QPlainTextEdit
{
background-color:#ffffff;
color:#4C4F69;
border:1px solid rgba(30, 102, 245, 0.2);
border-radius:8px;
padding:12px;
font-family:"Share Tech Mono","Consolas","Courier New","Microsoft YaHei","Malgun Gothic","SimSun",monospace;
font-size:13px;
selection-background-color:#8839EF;
selection-color:#ffffff
}

QTextEdit:focus,QPlainTextEdit:focus
{
border:1px solid rgba(30, 102, 245, 0.5);
background-color:#ffffff
}

QLabel#OutputTitle
{
font-size:20px;
color:#1E66F5;
letter-spacing:1.2px;
margin-bottom:4px;
text-transform:uppercase
}

QLabel#EnvTitleLabel
{
font-size:20px;
color:#1E66F5;
letter-spacing:.8px;
margin-bottom:6px
}

QLabel#EnvLabel
{
font-size:14px;
color:#4C4F69;
padding:2px 0
}

QScrollBar:vertical
{
background:transparent;
width:6px;
margin:0
}

QScrollBar::handle:vertical
{
background:rgba(30, 102, 245, 0.4);
min-height:20px;
border-radius:3px
}

QScrollBar::handle:vertical:hover
{
background:rgba(30, 102, 245, 0.8)
}

QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical
{
height:0
}

QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical
{
background:none
}

QScrollArea
{
background-color:transparent;
border:none
}

QScrollArea#ChangelogArea QScrollBar:vertical
{
width:4px
}

QCheckBox
{
spacing:8px;
color:#4C4F69;
background-color:transparent
}

QCheckBox::indicator
{
width:18px;
height:18px;
border-radius:4px;
border:2px solid #8839EF;
background-color:rgba(239, 241, 245, 0.9)
}

QCheckBox::indicator:checked
{
background-color:#8839EF
}

QLabel
{
background-color:transparent;
color:#4C4F69
}

QLabel#TitleLabel
{
font-size:26px;
font-weight:800;
color:#4C4F69;
letter-spacing:.5px
}

QLabel#SubtitleLabel
{
font-size:18px;
font-weight:600
}

QLabel#ClockLabel
{
font-family:"JetBrains Mono","Cascadia Code",monospace;
font-size:50px;
font-weight:400;
color:#1E66F5
}

QLabel#LinkLabel
{
color:#8839EF;
text-decoration:underline
}

QScrollArea#ChangelogArea
{
background-color:rgba(239, 241, 245, 0.85);
border:1px solid rgba(136, 57, 239, 0.3);
border-radius:10px
}

QTextBrowser#ChangelogContent
{
background-color:rgba(239, 241, 245, 0.9);
color:rgba(76, 79, 105, 0.6);
font-size:14px;
line-height:1.6em;
padding:12px;
border-radius:8px
}

QLabel#ChangelogTitleLabel
{
font-size:26px;
color:#1E66F5;
margin-bottom:12px;
letter-spacing:1.2px;
text-transform:uppercase
}

QLabel#FilePathLabel
{
color:rgba(76, 79, 105, 0.6);
border:1px solid rgba(136, 57, 239, 0.3);
border-radius:10px;
padding:8px;
font-family:"Consolas",monospace
}

QProgressBar
{
border:none;
background-color:rgba(76, 79, 105, 0.1);
border-radius:2px
}

QProgressBar::chunk
{
background-color:#8839EF;
border-radius:2px
}

QFrame#ModeSelectorFrame
{
background-color:rgba(239, 241, 245, 0.85);
border:1.5px solid #8839EF;
border-radius:12px;
padding:0;
margin:0
}

QLabel#ModeLabel
{
font-size:14px;
background:transparent;
padding:0;
margin:0
}

QLabel#ModeLabel[active="true"]
{
color:#1E66F5;
font-weight:bold
}

QLabel#ModeLabel[active="false"]
{
color:rgba(76, 79, 105, 0.6);
font-weight:normal
}

QComboBox
{
background-color:rgba(239, 241, 245, 0.9);
color:#4C4F69;
border:1px solid rgba(136, 57, 239, 0.3);
border-radius:8px;
padding:6px 12px;
min-height:30px
}

QComboBox:hover
{
background-color:rgba(239, 241, 245, 1.0);
border:1px solid rgba(136, 57, 239, 0.5)
}

QComboBox:focus
{
border:1px solid #8839EF
}

QComboBox::drop-down
{
border:none;
width:30px
}

QComboBox QAbstractItemView
{
background-color:#EFF1F5;
border:1.5px solid #8839EF;
border-radius:8px;
selection-background-color:#8839EF;
selection-color:#ffffff;
outline:none;
padding:4px
}

QComboBox QAbstractItemView::item
{
padding:10px;
border-radius:4px;
color:#4C4F69
}

QComboBox QAbstractItemView::item:selected
{
background-color:#8839EF;
color:#ffffff
}
"""

def register():
    return CatppuccinLatte()
