import platform
import ctypes
from ctypes import c_int, c_void_p, Structure, POINTER, byref, sizeof, windll
from PySide6.QtWidgets import QMainWindow, QWidget
from PySide6.QtCore import Qt, QEvent, QObject, QTimer

# =============================================================================
# Windows API Structures and Constants
# =============================================================================

class ACCENT_POLICY(Structure):
    _fields_ = [
        ("AccentState", c_int),
        ("AccentFlags", c_int),
        ("GradientColor", c_int),
        ("AnimationId", c_int)
    ]

class WINDOWCOMPOSITIONATTRIBDATA(Structure):
    _fields_ = [
        ("Attribute", c_int),
        ("Data", POINTER(ACCENT_POLICY)),
        ("SizeOfData", c_int)
    ]

# Accent States
ACCENT_DISABLED = 0
ACCENT_ENABLE_GRADIENT = 1
ACCENT_ENABLE_TRANSPARENTGRADIENT = 2
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4 
ACCENT_INVALID_STATE = 5

# Window Composition Attributes
WCA_ACCENT_POLICY = 19

# DWM Attributes
DWMWA_USE_IMMERSIVE_DARK_MODE = 20 
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19

# =============================================================================
# Helper Functions
# =============================================================================

def _get_windows_accent_color() -> tuple[int, int, int]:
    try:
        import winreg
        registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\DWM")
        value, _ = winreg.QueryValueEx(key, "ColorizationColor")
        winreg.CloseKey(key)
        r = (value >> 16) & 0xFF
        g = (value >> 8) & 0xFF
        b = value & 0xFF
        return (r, g, b)
    except Exception:
        return (0, 120, 215) # Default Windows Blue

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Converts hex string (#RRGGBB) to (r, g, b)."""
    if not isinstance(hex_color, str):
        return (30, 30, 30)
    
    hex_color = hex_color.lstrip('#')
    try:
        if len(hex_color) == 6:
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        elif len(hex_color) == 3:
             return tuple(int(hex_color[i]*2, 16) for i in (0, 1, 2))
    except ValueError:
        pass
    return (30, 30, 30) # Default fallback

def _luminance(color: tuple[int, int, int]) -> float:
    """Calculates luminance of an RGB color (0.0 - 255.0)."""
    return 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]

def _soft_blur_blend(accent_rgb, bg_rgb, primary_rgb) -> tuple[int, int, int]:
    """
    - Background dominates (70-85%)
    - Accent is subtle (5-15%)
    - Primary color adds highlight (5-10%)
    - Applies dynamic desaturation + vibrance boost for more natural acrylic
    """
    bg_lum = _luminance(bg_rgb)
    
    # Dynamic weights based on luminance
    if bg_lum < 64:  # very dark theme
        bg_weight, accent_weight, primary_weight = 0.85, 0.10, 0.05
    elif bg_lum < 128:  # dark
        bg_weight, accent_weight, primary_weight = 0.80, 0.12, 0.08
    elif bg_lum < 192:  # light
        bg_weight, accent_weight, primary_weight = 0.75, 0.15, 0.10
    else:  # very light
        bg_weight, accent_weight, primary_weight = 0.70, 0.20, 0.10

    r = bg_rgb[0]*bg_weight + accent_rgb[0]*accent_weight + primary_rgb[0]*primary_weight
    g = bg_rgb[1]*bg_weight + accent_rgb[1]*accent_weight + primary_rgb[1]*primary_weight
    b = bg_rgb[2]*bg_weight + accent_rgb[2]*accent_weight + primary_rgb[2]*primary_weight

    # Desaturation towards neutral pastel
    avg = (r + g + b) / 3
    r = int(r*0.85 + avg*0.15)
    g = int(g*0.85 + avg*0.15)
    b = int(b*0.85 + avg*0.15)

    fade = 0.75 + (0.05 if bg_lum < 64 else 0)
    return int(r*fade), int(g*fade), int(b*fade)


def _calculate_opacity(lum: float) -> int:
    """
    - Dark themes: slightly higher alpha for readability
    - Light themes: lower alpha for glass-like transparency
    - Range: 0x50 (~31%) to 0x80 (~50%) for more see-through feel
    """
    lum = max(0, min(255, lum))  # clamp

    if lum < 64:  # very dark
        alpha = 0x70
    elif lum < 128:  # dark
        alpha = 0x68
    elif lum < 192:  # light
        alpha = 0x5F
    else:  # very light
        alpha = 0x50

    return alpha

def _calculate_dynamic_blur_color(theme_colors: dict) -> int:
    """Calculates final ARGB blur color"""
    accent_rgb = _get_windows_accent_color()
    bg_rgb = _hex_to_rgb(theme_colors.get("background", "#1E1E1E"))
    primary_rgb = _hex_to_rgb(theme_colors.get("primary", "#0078D7"))

    r, g, b = _soft_blur_blend(accent_rgb, bg_rgb, primary_rgb)
    lum = _luminance((r, g, b))
    opacity = _calculate_opacity(lum)
    return (opacity << 24) | (b << 16) | (g << 8) | r


# =============================================================================
# Helper Class for Dynamic Updates
# =============================================================================

class DynamicBlurEventFilter(QObject):
    def __init__(self, win, color, force_dark):
        super().__init__(win)
        self.window = win
        self.blur_color = color
        self.force_dark = force_dark
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._apply)
    
    def update_params(self, color, force_dark):
        self.blur_color = color
        self.force_dark = force_dark
        self._apply()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.WindowActivate):
            self._timer.start()
        return False
    
    def _apply(self):
        _apply_blur_color(self.window, self.blur_color)
        _apply_dark_mode(self.window, self.force_dark)

# =============================================================================
# Main API
# =============================================================================

def enable_dynamic_blur(window: QMainWindow, theme_colors: dict = None):
    if platform.system() != "Windows":
        return
        
    # Check Windows Version 
    try:
        version_parts = platform.version().split('.')
        if len(version_parts) >= 3:
            build = int(version_parts[2])
            if build < 17134:
                return # Not supported
    except Exception:
        pass

    if theme_colors is None:
        theme_colors = {}

    blur_color = _calculate_dynamic_blur_color(theme_colors)
    
    r = blur_color & 0xFF
    g = (blur_color >> 8) & 0xFF
    b = (blur_color >> 16) & 0xFF
    
    lum = _luminance((r, g, b))
    
    # If background is bright (lum > 128), text should be dark -> force_dark = False
    # If background is dark (lum <= 128), text should be light -> force_dark = True
    accent_rgb = _get_windows_accent_color()
    accent_lum = _luminance(accent_rgb)
    force_dark_mode = lum <= 128 or accent_lum < 96

    window.setAttribute(Qt.WA_TranslucentBackground, True)
    style = window.styleSheet()
    if "QMainWindow { background-color: transparent; }" not in style:
        window.setStyleSheet(style + "\nQMainWindow { background-color: transparent; }")

    if not hasattr(window, "_blur_filter") or not isinstance(window._blur_filter, DynamicBlurEventFilter):
        if hasattr(window, "_blur_filter"):
            window.removeEventFilter(window._blur_filter)
        
        window._blur_filter = DynamicBlurEventFilter(window, blur_color, force_dark_mode)
        window.installEventFilter(window._blur_filter)
    else:
        window._blur_filter.update_params(blur_color, force_dark_mode)
    
    _apply_blur_color(window, blur_color)
    _apply_dark_mode(window, force_dark_mode)
    window.repaint()

def disable_blur(window: QMainWindow):
    if hasattr(window, "_blur_filter"):
        window.removeEventFilter(window._blur_filter)
        del window._blur_filter
    
    window.setAttribute(Qt.WA_TranslucentBackground, False)
    _apply_blur_color(window, 0, enabled=False)
    window.repaint()

def _apply_blur_color(window: QMainWindow, color: int, enabled: bool = True):
    try:
        hwnd = int(window.winId())
        user32 = windll.user32
        
        set_window_composition_attribute = user32.SetWindowCompositionAttribute
        set_window_composition_attribute.argtypes = [c_void_p, POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
        set_window_composition_attribute.restype = c_int

        accent = ACCENT_POLICY()
        if enabled:
            accent.AccentState = ACCENT_ENABLE_ACRYLICBLURBEHIND
            accent.AccentFlags = 2
            accent.GradientColor = color
        else:
            accent.AccentState = ACCENT_DISABLED

        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = WCA_ACCENT_POLICY
        data.SizeOfData = sizeof(accent)
        data.Data = ctypes.pointer(accent)

        set_window_composition_attribute(hwnd, byref(data))
    except Exception:
        pass

def _apply_dark_mode(window: QMainWindow, enabled: bool):
    """Forces Windows to use dark mode for the title bar."""
    try:
        hwnd = int(window.winId())
        dwmapi = windll.dwmapi
        
        darkMode = c_int(1 if enabled else 0)
        
        res = dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, byref(darkMode), sizeof(darkMode))
        if res != 0:
            dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD, byref(darkMode), sizeof(darkMode))
    except Exception:
        pass
