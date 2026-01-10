"""
De4py UI Constants - Colors, Fonts, Spacing, Animation
"""

# Colors
COLOR_BG_DARK = "#0f0f0f"
COLOR_BG_FRAME = "#1f1f1f"
COLOR_BG_INPUT = "#222222"
COLOR_BG_INPUT_HOVER = "#333333"
COLOR_BG_INPUT_FOCUS = "#444444"
COLOR_ACCENT = "#0287CF"
COLOR_ACCENT_HOVER = "#4ba3e2"
COLOR_ACCENT_DIM = "#0287cf55"
COLOR_TEXT = "#ffffff"
COLOR_TEXT_DIM = "#ffffffaa"
COLOR_NAVBAR_BG = "#55555511"
COLOR_OVERLAY = "rgba(0, 0, 0, 0.5)"

# Fonts
FONT_FAMILY_MONO = "Share Tech Mono, Consolas, JetBrains Mono, monospace"
FONT_FAMILY_UI = "Segoe UI, Inter, sans-serif"
FONT_SIZE_NORMAL = 14
FONT_SIZE_LARGE = 16
FONT_SIZE_TITLE = 24
FONT_SIZE_CLOCK = 48

# Spacing
SPACING_XS = 5
SPACING_SM = 10
SPACING_MD = 20
SPACING_LG = 40

# Sizing
SIDEBAR_WIDTH = 240
SIDEBAR_WIDTH_COLLAPSED = 0
HAMBURGER_SIZE = 50
BUTTON_PADDING_H = 20
BUTTON_PADDING_V = 10
BUTTON_RADIUS = 6
FRAME_RADIUS = 10
FRAME_BORDER = 2
INPUT_RADIUS = 10

# Animation
ANIM_DURATION_FAST = 150
ANIM_DURATION_NORMAL = 200
ANIM_DURATION_SLOW = 250

# Window
WINDOW_WIDTH = 1024
WINDOW_HEIGHT = 589
WINDOW_TITLE = "de4py"

# Notification
NOTIF_WIDTH = 300
NOTIF_DURATION = 3500
NOTIF_PROGRESS_DURATION = 3000

# Screen IDs
SCREEN_HOME = 0
SCREEN_DEOBFUSCATOR = 1
SCREEN_PYSHELL = 2
SCREEN_BEHAVIOR_MONITOR = 3
SCREEN_ANALYZER = 4
SCREEN_PLUGINS = 5
SCREEN_SETTINGS = 6
SCREEN_ABOUT = 7

# Navigation items (id, label, icon)
NAV_ITEMS = [
    ("home", "Home", "home.svg"),
    ("deobfuscator", "Deobfuscator", "layers.svg"),
    ("pyshell", "PyShell", "terminal.svg"),
    ("analyzer", "Analyzer", "file-text.svg"),
    ("plugins", "Plugins", "grid.svg"),
    ("settings", "Settings", "settings.svg"),
    ("about", "About", "info.svg"),
]
