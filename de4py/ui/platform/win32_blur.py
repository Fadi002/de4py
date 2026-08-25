# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import platform
import ctypes
import sys
from ctypes import c_int, c_void_p, c_ulong, Structure, POINTER, byref, sizeof
if platform.system() == "Windows":
    from ctypes import windll
else:
    windll = None
from PySide6.QtWidgets import QMainWindow

from de4py.lang import tr
from de4py.lang.keys import (
    MSG_WINDOWS_TRANSPARENCY_OFF, MSG_TRANSPARENCY_AUTO_ENABLED,
)
from PySide6.QtCore import Qt, QEvent, QObject, QTimer

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


ACCENT_DISABLED = 0
ACCENT_ENABLE_GRADIENT = 1
ACCENT_ENABLE_TRANSPARENTGRADIENT = 2
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
ACCENT_INVALID_STATE = 5

WCA_ACCENT_POLICY = 19

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19

GWL_STYLE = -16
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_THICKFRAME = 0x00040000

SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020

def _get_build_number() -> int:
    try:
        return int(sys.getwindowsversion().build)
    except Exception:
        pass
    try:
        parts = platform.version().split('.')
        return int(parts[2])
    except Exception:
        return 0


def _system_transparency_enabled() -> bool:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "EnableTransparency")
        winreg.CloseKey(key)
        return bool(value)
    except FileNotFoundError:
        return True
    except Exception:
        return True


_TRANSPARENCY_WARNED = False
_TRANSPARENCY_OVERRIDDEN = None


def _read_transparency_setting():
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            0, winreg.KEY_READ | winreg.KEY_WRITE)
        value, _ = winreg.QueryValueEx(key, "EnableTransparency")
        winreg.CloseKey(key)
        return int(value)
    except Exception:
        return None


def _write_transparency_setting(value: int) -> bool:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "EnableTransparency", 0, winreg.REG_DWORD, value)
        winreg.CloseKey(key)
    except Exception:
        return False
    try:
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        result = c_ulong(0)
        windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Theme",
            SMTO_ABORTIFHUNG, 1000, byref(result))
    except Exception:
        pass
    return True


def ensure_system_transparency(window: QMainWindow) -> bool:
    """True when DWM will render glass materials. Temporarily flips the OS
    transparency switch on if the user had it disabled, remembering the old
    value for restore_system_transparency()."""
    global _TRANSPARENCY_OVERRIDDEN
    if _system_transparency_enabled():
        return True

    previous = _read_transparency_setting()
    if previous is not None and _write_transparency_setting(1):
        _TRANSPARENCY_OVERRIDDEN = previous
        try:
            window.show_notification("info", tr(MSG_TRANSPARENCY_AUTO_ENABLED))
        except Exception:
            pass
        return True

    global _TRANSPARENCY_WARNED
    if not _TRANSPARENCY_WARNED:
        _TRANSPARENCY_WARNED = True
        try:
            window.show_notification(
                "warning", tr(MSG_WINDOWS_TRANSPARENCY_OFF))
        except Exception:
            pass
    return False


def restore_system_transparency():
    global _TRANSPARENCY_OVERRIDDEN
    if _TRANSPARENCY_OVERRIDDEN is None:
        return
    _write_transparency_setting(_TRANSPARENCY_OVERRIDDEN)
    _TRANSPARENCY_OVERRIDDEN = None


def set_high_precision_timer(enabled: bool):
    try:
        winmm = ctypes.windll.winmm
        if enabled:
            winmm.timeBeginPeriod(1)
        else:
            winmm.timeEndPeriod(1)
    except Exception:
        pass

class MARGINS(Structure):
    _fields_ = [
        ("cxLeftWidth", c_int),
        ("cxRightWidth", c_int),
        ("cyTopHeight", c_int),
        ("cyBottomHeight", c_int)
    ]

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
        return (0, 120, 215)  # Default Windows Blue

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
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
    return (30, 30, 30)

def _luminance(color: tuple[int, int, int]) -> float:
    return 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]

def _soft_blur_blend(accent_rgb, bg_rgb, primary_rgb) -> tuple[int, int, int]:
    """
    - Background dominates (70-85%)
    - Accent is subtle (5-15%)
    - Primary color adds highlight (5-10%)
    - Applies dynamic desaturation + vibrance boost for more natural acrylic
    """
    bg_lum = _luminance(bg_rgb)

    if bg_lum < 64:
        bg_weight, accent_weight, primary_weight = 0.85, 0.10, 0.05
    elif bg_lum < 128:
        bg_weight, accent_weight, primary_weight = 0.80, 0.12, 0.08
    elif bg_lum < 192:
        bg_weight, accent_weight, primary_weight = 0.75, 0.15, 0.10
    else:
        bg_weight, accent_weight, primary_weight = 0.70, 0.20, 0.10

    blend_r = bg_rgb[0]*bg_weight + accent_rgb[0]*accent_weight + primary_rgb[0]*primary_weight
    blend_g = bg_rgb[1]*bg_weight + accent_rgb[1]*accent_weight + primary_rgb[1]*primary_weight
    blend_b = bg_rgb[2]*bg_weight + accent_rgb[2]*accent_weight + primary_rgb[2]*primary_weight

    avg = (blend_r + blend_g + blend_b) / 3
    blend_r = int(blend_r*0.85 + avg*0.15)
    blend_g = int(blend_g*0.85 + avg*0.15)
    blend_b = int(blend_b*0.85 + avg*0.15)

    fade = 0.75 + (0.05 if bg_lum < 64 else 0)
    return int(blend_r*fade), int(blend_g*fade), int(blend_b*fade)


def _calculate_opacity(lum: float) -> int:
    """
    - Dark themes: slightly higher alpha for readability
    - Light themes: lower alpha for glass-like transparency
    - Range: 0x50 (~31%) to 0x80 (~50%) for more see-through feel
    """
    lum = max(0, min(255, lum))

    if lum < 64:
        alpha = 0x70
    elif lum < 128:
        alpha = 0x68
    elif lum < 192:
        alpha = 0x5F
    else:
        alpha = 0x50

    return alpha

def _calculate_dynamic_blur_color(theme_colors: dict) -> int:
    accent_rgb = _get_windows_accent_color()
    bg_rgb = _hex_to_rgb(theme_colors.get("background", "#1E1E1E"))
    primary_rgb = _hex_to_rgb(theme_colors.get("primary", "#0078D7"))

    r, g, b = _soft_blur_blend(accent_rgb, bg_rgb, primary_rgb)
    lum = _luminance((r, g, b))
    opacity = _calculate_opacity(lum)
    return (opacity << 24) | (b << 16) | (g << 8) | r


class DynamicBlurEventFilter(QObject):
    def __init__(self, win, color, force_dark):
        super().__init__(win)
        self.window = win
        self.blur_color = color
        self.force_dark = force_dark
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(50)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._apply)

    def update_params(self, color, force_dark):
        self.blur_color = color
        self.force_dark = force_dark
        self._apply()

    def eventFilter(self, obj, event):
        # Accent state persists across resize/move; re-applying SWCA there
        # forces DWM layer rebuilds mid-animation and smears moving elements.
        if event.type() in (QEvent.Type.WindowActivate, QEvent.Type.WindowDeactivate):
            self._timer.start()
        return False

    def _apply(self):
        _apply_blur_color(self.window, self.blur_color)
        _apply_dark_mode(self.window, self.force_dark)

_TRANSPARENCY_WARNED = False


def enable_dynamic_blur(window: QMainWindow, theme_colors: dict = None) -> bool:
    global _TRANSPARENCY_WARNED
    if platform.system() != "Windows":
        return False

    try:
        version_parts = platform.version().split('.')
        if len(version_parts) >= 3:
            build = int(version_parts[2])
            if build < 17134:
                return False
    except Exception:
        pass

    if not ensure_system_transparency(window):
        return False

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

    try:
        hwnd = int(window.winId())
        user32 = ctypes.windll.user32

        style = user32.GetWindowLongW(hwnd, GWL_STYLE)

        style &= ~WS_CAPTION
        style &= ~WS_SYSMENU
        if _get_build_number() < 22000:
            # Windows 10: dropping THICKFRAME avoids the white unfocused border.
            # Windows 11: KEEP it — DWM needs it to host the accent-acrylic
            # composition; removing it turns the effect into a black pane.
            style &= ~WS_THICKFRAME

        user32.SetWindowLongW(hwnd, GWL_STYLE, style)

        # Ensure shadow stays even without thick frame
        dwmapi = ctypes.windll.dwmapi
        policy = c_int(2)  # DWMNCRP_ENABLED
        dwmapi.DwmSetWindowAttribute(hwnd, 2, byref(policy), sizeof(policy))

        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
    except Exception:
        pass

    # Apply blur after style change to ensure correct context
    _apply_blur_color(window, blur_color)
    _apply_dark_mode(window, force_dark_mode)

    window.repaint()
    return True

def disable_blur(window: QMainWindow):
    restore_system_transparency()
    if hasattr(window, "_blur_filter"):
        window.removeEventFilter(window._blur_filter)
        del window._blur_filter

    window.setAttribute(Qt.WA_TranslucentBackground, False)
    _apply_blur_color(window, 0, enabled=False)

    try:
        hwnd = int(window.winId())
        user32 = ctypes.windll.user32

        user32.GetWindowLongW(hwnd, GWL_STYLE)
        exstyle = user32.GetWindowLongW(hwnd, -20)

        user32.SetWindowLongW(hwnd, GWL_STYLE, 0x00CF0000)
        user32.SetWindowLongW(hwnd, -20, exstyle & ~0x00080000)

        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
    except Exception:
        pass

    window.repaint()

def _apply_blur_color(window: QMainWindow, color: int, enabled: bool = True):
    try:
        hwnd = int(window.winId())
        user32 = windll.user32

        if not enabled:
            _apply_accent_policy(user32, hwnd, 0, False)
            return

        accent_color = color
        if not window.isActiveWindow():
            a = (color >> 24) & 0xFF
            r = color & 0xFF
            g = (color >> 8) & 0xFF
            b = (color >> 16) & 0xFF

            new_a = min(0xAA, a + 0x30)
            accent_color = (new_a << 24) | (b << 16) | (g << 8) | r

        _apply_accent_policy(user32, hwnd, accent_color, True)
    except Exception:
        pass


def _apply_accent_policy(user32, hwnd, color: int, enabled: bool):
    user32.SetWindowCompositionAttribute.argtypes = [c_void_p, POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
    user32.SetWindowCompositionAttribute.restype = c_int

    accent = ACCENT_POLICY()
    if enabled:
        accent.AccentState = ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.AccentFlags = 0x20 | 0x40 | 0x80 | 0x100
        accent.GradientColor = color
    else:
        accent.AccentState = ACCENT_DISABLED

    data = WINDOWCOMPOSITIONATTRIBDATA()
    data.Attribute = WCA_ACCENT_POLICY
    data.SizeOfData = sizeof(accent)
    data.Data = ctypes.pointer(accent)

    user32.SetWindowCompositionAttribute(hwnd, byref(data))

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
