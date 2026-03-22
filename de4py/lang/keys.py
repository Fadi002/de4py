# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Translation Key Constants
==========================
Centralized constants for all translation keys.
Using constants prevents typos and enables IDE autocomplete.
"""

# =============================================================================
# Global
# =============================================================================
APP_NAME = "common.app_name"

# =============================================================================
# Navigation

# =============================================================================
NAV_HOME = "nav.home"
NAV_DEOBFUSCATOR = "nav.deobfuscator"
NAV_PYSHELL = "nav.pyshell"
NAV_ANALYZER = "nav.analyzer"
NAV_PLUGINS = "nav.plugins"
NAV_PYLINGUAL = "nav.pylingual"
NAV_SETTINGS = "nav.settings"
NAV_ABOUT = "nav.about"

# =============================================================================
# Screen Titles
# =============================================================================
SCREEN_TITLE_HOME = "screen.home.title"
SCREEN_TITLE_DEOBFUSCATOR = "screen.deobfuscator.title"
SCREEN_TITLE_PYSHELL = "screen.pyshell.title"
SCREEN_TITLE_ANALYZER = "screen.analyzer.title"
SCREEN_TITLE_PLUGINS = "screen.plugins.title"
SCREEN_TITLE_PYLINGUAL = "screen.pylingual.title"
SCREEN_TITLE_SETTINGS = "screen.settings.title"
SCREEN_TITLE_ABOUT = "screen.about.title"
SCREEN_TITLE_BEHAVIOR = "screen.behavior.title"

# =============================================================================
# Home Screen
# =============================================================================
HOME_CHANGELOG_TITLE = "screen.home.changelog"
HOME_ENV_INFO = "screen.home.env_info"
HOME_PYTHON_VERSION = "screen.home.python_version"
HOME_ARCH = "screen.home.arch"
HOME_OS = "screen.home.os"

# =============================================================================
# Settings Screen
# =============================================================================
SETTINGS_LANGUAGE = "screen.settings.language"
SETTINGS_RPC = "screen.settings.rpc"
SETTINGS_STEALTH = "screen.settings.stealth"
SETTINGS_PLUGINS = "screen.settings.plugins"
SETTINGS_TRANSPARENT_UI = "screen.settings.transparent"
SETTINGS_RESTART_NOTE = "screen.settings.restart_note"

# =============================================================================
# Deobfuscator Screen
# =============================================================================
DEOBF_SELECT_FILE = "screen.deobfuscator.select_file"
DEOBF_DEOBFUSCATE = "screen.deobfuscator.deobfuscate"
DEOBF_OUTPUT = "screen.deobfuscator.output"
DEOBF_PROCESSING = "screen.deobfuscator.processing"
DEOBF_RESEARCH_NOTE = "screen.deobfuscator.research_note"

# =============================================================================
# PyShell Screen
# =============================================================================
PYSHELL_ATTACH = "screen.pyshell.attach"
PYSHELL_DETACH = "screen.pyshell.detach"
PYSHELL_EXECUTE = "screen.pyshell.execute"
PYSHELL_CLEAR = "screen.pyshell.clear"
PYSHELL_INPUT_PLACEHOLDER = "screen.pyshell.input_placeholder"
PYSHELL_PID_LABEL = "screen.pyshell.pid_label"
PYSHELL_COMMANDS_TITLE = "screen.pyshell.commands_title"
PYSHELL_CMD_EXEC_PY = "screen.pyshell.cmd.exec_py"
PYSHELL_CMD_CRASH = "screen.pyshell.cmd.crash"
PYSHELL_CMD_FUNCTIONS = "screen.pyshell.cmd.functions"
PYSHELL_CMD_SHOW_CONSOLE = "screen.pyshell.cmd.show_console"
PYSHELL_CMD_GUI = "screen.pyshell.cmd.gui"
PYSHELL_CMD_DUMP_STRINGS = "screen.pyshell.cmd.dump_strings"
PYSHELL_CMD_DEL_EXIT = "screen.pyshell.cmd.del_exit"
PYSHELL_CMD_DETACH = "screen.pyshell.cmd.detach"
PYSHELL_CMD_BEHAVIOR = "screen.pyshell.cmd.behavior"
PYSHELL_INJECTED = "screen.pyshell.msg.injected"
PYSHELL_INJECT_FAIL = "screen.pyshell.msg.inject_failed"
PYSHELL_PROCESS_DIED = "screen.pyshell.msg.process_died"
PYSHELL_NEED_INJECT = "screen.pyshell.msg.need_inject"
PYSHELL_ENTER_PID = "screen.pyshell.msg.enter_pid"
PYSHELL_INJECTOR_FAILED = "screen.pyshell.msg.injector_failed"
PYSHELL_CMD_EXECUTED = "screen.pyshell.msg.cmd_executed"
PYSHELL_CMD_SAVED_AS = "screen.pyshell.msg.saved_as"
PYSHELL_CMD_EXECUTED_MSG = "screen.pyshell.msg.executed_msg"
PYSHELL_CMD_DLL_DETACHED = "screen.pyshell.msg.dll_detached"
PYSHELL_CMD_BEHAVIOR_HINT = "screen.pyshell.msg.behavior_hint"
PYSHELL_CMD_DONE = "screen.pyshell.msg.done"
PYSHELL_CMD_FAILED = "screen.pyshell.msg.failed"
PYSHELL_BTN_STEALTH = "screen.pyshell.btn.stealth"



# =============================================================================
# Analyzer Screen
# =============================================================================
ANALYZER_SELECT_FILE = "screen.analyzer.select_file"
ANALYZER_ANALYZE = "screen.analyzer.analyze"
ANALYZER_RESULTS = "screen.analyzer.results"
ANALYZER_OPTIONS_TITLE = "screen.analyzer.options_title"
ANALYZER_CMD_PACKER = "screen.analyzer.cmd.packer"
ANALYZER_CMD_UNPACK = "screen.analyzer.cmd.unpack"
ANALYZER_CMD_SUS_STRINGS = "screen.analyzer.cmd.sus_strings"
ANALYZER_CMD_ALL_STRINGS = "screen.analyzer.cmd.all_strings"
ANALYZER_CMD_HASHES = "screen.analyzer.cmd.hashes"
ANALYZER_ONLY_EXE = "screen.analyzer.msg.only_exe"
ANALYZER_EXECUTED = "screen.analyzer.msg.executed"


# =============================================================================
# Plugins Screen
# =============================================================================
PLUGINS_INSTALLED = "screen.plugins.installed"
PLUGINS_APPLY = "screen.plugins.apply"
PLUGINS_RESET = "screen.plugins.reset"
PLUGINS_NO_PLUGINS = "screen.plugins.no_plugins"
PLUGINS_DISABLED = "screen.plugins.disabled"
PLUGINS_NONE_LOADED = "screen.plugins.none_loaded"
PLUGINS_FAILED_LOAD = "screen.plugins.failed_load"
PLUGINS_MADE_BY = "screen.plugins.made_by"
PLUGINS_TYPE = "screen.plugins.type"
PLUGINS_THEME_APPLIED = "screen.plugins.msg.theme_applied"
PLUGINS_THEME_FAILED = "screen.plugins.msg.theme_failed"
PLUGINS_THEME_RESET = "screen.plugins.msg.theme_reset"


# =============================================================================
# PyLingual Screen
# =============================================================================
PYLINGUAL_MODE_OFFLINE = "screen.pylingual.mode_offline"
PYLINGUAL_MODE_ONLINE = "screen.pylingual.mode_online"
PYLINGUAL_OFFLINE = "screen.pylingual.mode_offline"
PYLINGUAL_ONLINE = "screen.pylingual.mode_online"
PYLINGUAL_SELECT_FILE = "screen.pylingual.select_file"
PYLINGUAL_DECOMPILE = "screen.pylingual.decompile"
PYLINGUAL_EXECUTE = "screen.pylingual.decompile"
PYLINGUAL_PROGRESS = "screen.pylingual.progress"
PYLINGUAL_COPY = "common.btn.copy"
PYLINGUAL_RESULT = "screen.pylingual.result"
PYLINGUAL_TOS_TITLE = "screen.pylingual.tos_title"
PYLINGUAL_TOS_ACCEPTANCE = "screen.pylingual.tos_acceptance"
PYLINGUAL_TOS_CONTENT = "screen.pylingual.tos_content"
PYLINGUAL_CANCEL = "common.btn.cancel"
PYLINGUAL_I_ACCEPT = "common.btn.ok"
PYLINGUAL_TOOLTIP_SELECT = "screen.pylingual.tooltip.select"
PYLINGUAL_TOOLTIP_EXECUTE = "screen.pylingual.tooltip.execute"
PYLINGUAL_TOOLTIP_COPY = "screen.pylingual.tooltip.copy"
PYLINGUAL_MSG_INITIALIZING = "screen.pylingual.msg.initializing"
PYLINGUAL_MSG_OFFLINE_LIMIT = "screen.pylingual.msg.offline_limit"
PYLINGUAL_MSG_COMPLETE = "screen.pylingual.msg.complete"
PYLINGUAL_MSG_CACHED = "screen.pylingual.msg.cached"
PYLINGUAL_PLACEHOLDER_RESULT = "screen.pylingual.placeholder.result"
PYLINGUAL_PLACEHOLDER_SELECTED = "screen.pylingual.placeholder.selected"



# =============================================================================
# Behavior Monitor Screen
# =============================================================================
BEHAVIOR_START = "screen.behavior.start"
BEHAVIOR_STOP = "screen.behavior.stop"
BEHAVIOR_NO_PROCESS = "screen.behavior.no_process"
BM_MONITOR_OPTIONS = "screen.behavior.options"
BM_MONITOR_FILES = "screen.behavior.monitor_files"
BM_MONITOR_PROCESSES = "screen.behavior.monitor_processes"
BM_MONITOR_CONNECTIONS = "screen.behavior.monitor_connections"
BM_DUMP_SOCKET = "screen.behavior.dump_socket"
BM_DUMP_SSL = "screen.behavior.dump_ssl"
BM_PYC_DUMPER = "screen.behavior.pyc_dumper"
BM_BACK_TO_MENU = "screen.behavior.back_to_menu"


# =============================================================================
# About Screen
# =============================================================================
ABOUT_VERSION = "screen.about.version"
ABOUT_BUILD = "screen.about.build"
ABOUT_CREDITS = "screen.about.credits"
ABOUT_GITHUB = "screen.about.github"
ABOUT_DISCORD = "screen.about.discord"

# =============================================================================
# Common UI Elements
# =============================================================================
BTN_APPLY = "common.btn.apply"
BTN_CANCEL = "common.btn.cancel"
BTN_OK = "common.btn.ok"
BTN_BROWSE = "common.btn.browse"
BTN_SAVE = "common.btn.save"
BTN_CLOSE = "common.btn.close"
BTN_RESET = "common.btn.reset"
BTN_COPY = "common.btn.copy"
BTN_COPY_OUTPUT = "common.btn.copy_output"
BTN_CLEAR = "common.btn.clear"
LBL_OUTPUT = "common.lbl.output"


# =============================================================================
# Common Messages
# =============================================================================
MSG_LOADING = "common.msg.loading"
MSG_ERROR = "common.msg.error"
MSG_SUCCESS = "common.msg.success"
MSG_COPIED = "notification.copied"

MSG_WARNING = "common.msg.warning"
MSG_INFO = "common.msg.info"
MSG_CONFIRM = "common.msg.confirm"
MSG_NO_FILE_SELECTED = "common.msg.no_file_selected"
MSG_FILE_NOT_FOUND = "common.msg.file_not_found"
MSG_OPERATION_COMPLETE = "common.msg.operation_complete"
MSG_OPERATION_FAILED = "common.msg.operation_failed"

# =============================================================================
# Plural Forms
# =============================================================================
PLURAL_FILES = "plural.files"
PLURAL_ITEMS = "plural.items"
PLURAL_SECONDS = "plural.seconds"
PLURAL_MINUTES = "plural.minutes"

# =============================================================================
# Tooltips
# =============================================================================
TOOLTIP_HAMBURGER = "tooltip.hamburger"
TOOLTIP_COPY = "tooltip.copy"
TOOLTIP_CLEAR = "tooltip.clear"
TOOLTIP_PYSHELL_SELECT = "tooltip.pyshell.select"
TOOLTIP_PYSHELL_EXECUTE = "tooltip.pyshell.execute"


# =============================================================================
# Dialogs
# =============================================================================
DIALOG_FILE_SELECT = "dialog.file_select"
DIALOG_SAVE_AS = "dialog.save_as"
DIALOG_CONFIRM_EXIT = "dialog.confirm_exit"
DIALOG_VALUE_PLACEHOLDER = "dialog.value_placeholder"
DIALOG_VALUE_LABEL = "dialog.value_label"
DIALOG_SUBMIT_BTN = "dialog.submit_btn"


# =============================================================================
# Notifications
# =============================================================================
NOTIF_COPIED = "notification.copied"
NOTIF_SAVED = "notification.saved"
NOTIF_LANGUAGE_CHANGED = "notification.language_changed"

# =============================================================================
# DevTools
# =============================================================================
DEV_TITLE = "devtools.title"
DEV_TAB_APP = "devtools.tabs.app"
DEV_TAB_UI = "devtools.tabs.ui"
DEV_TAB_TREE = "devtools.tabs.tree"
DEV_TAB_SCENARIOS = "devtools.tabs.scenarios"
DEV_TAB_LOGS = "devtools.tabs.logs"
DEV_TAB_BACKEND = "devtools.tabs.backend"

DEV_UI_HIGHLIGHT = "devtools.ui.highlight"
DEV_UI_INSPECT = "devtools.ui.inspect"
DEV_UI_FPS = "devtools.ui.fps"
DEV_UI_ANIM_SPEED = "devtools.ui.anim_speed"
DEV_UI_STRESS_TITLE = "devtools.ui.stress_title"
DEV_UI_BREAK = "devtools.ui.break"
DEV_UI_AUTOFILL = "devtools.ui.autofill"
DEV_UI_PROP_INSPECTOR = "devtools.ui.prop_inspector"
DEV_UI_REFRESH = "devtools.ui.refresh"

DEV_PROP_CLASS = "devtools.prop.class"
DEV_PROP_NAME = "devtools.prop.name"
DEV_PROP_TEXT = "devtools.prop.text"
DEV_PROP_ENABLED = "devtools.prop.enabled"
DEV_PROP_VISIBLE = "devtools.prop.visible"
DEV_PROP_STYLE = "devtools.prop.style"
DEV_PROP_TOOLTIP = "devtools.prop.tooltip"
DEV_PROP_GEOMETRY = "devtools.prop.geometry"
DEV_PROP_HEADER_PROPERTY = "devtools.prop.header_property"
DEV_PROP_HEADER_VALUE = "devtools.prop.header_value"

DEV_TREE_SEARCH = "devtools.tree.search"
DEV_BACKEND_LATENCY = "devtools.backend.latency"
DEV_BACKEND_ERROR = "devtools.backend.error"
DEV_BACKEND_OFFLINE = "devtools.backend.offline"
DEV_BACKEND_CRASH = "devtools.backend.crash"
DEV_BACKEND_STATE_TITLE = "devtools.backend.state_title"
DEV_BACKEND_MODE_NORMAL = "devtools.backend.mode_normal"
DEV_BACKEND_MODE_FAIL = "devtools.backend.mode_fail"
DEV_BACKEND_MODE_EMPTY = "devtools.backend.mode_empty"
DEV_BACKEND_CONDITIONS_TITLE = "devtools.backend.conditions_title"
DEV_BACKEND_PRESET_SLOW3G = "devtools.backend.preset_slow3g"
DEV_BACKEND_PRESET_2GEDGE = "devtools.backend.preset_2gedge"

DEV_APP_FONT_SCALE = "devtools.app.font_scale"
DEV_APP_WINDOW_PRESETS = "devtools.app.window_presets"
DEV_APP_NAV_TITLE = "devtools.app.nav_title"
DEV_APP_PRESET_MOBILE = "devtools.app.preset_mobile"
DEV_APP_PRESET_TABLET = "devtools.app.preset_tablet"
DEV_APP_PRESET_DESKTOP = "devtools.app.preset_desktop"
DEV_APP_NOTIF_TITLE = "devtools.app.notif_title"
DEV_APP_LOAD_SIM = "devtools.app.load_sim"
DEV_APP_RUN = "devtools.app.run"
DEV_APP_SYSTEM_TITLE = "devtools.app.system_title"
DEV_APP_FONT_SIZE = "devtools.app.font_size"
DEV_APP_FORCE_RELOAD = "devtools.app.force_reload"

DEV_LOG_TITLE = "devtools.log.title"
DEV_LOG_FILTER = "devtools.log.filter"
DEV_LOG_STRESS = "devtools.log.stress"

DEV_TREE_TITLE = "devtools.tree.title"
DEV_TREE_HEADER_WIDGET = "devtools.tree.header_widget"
DEV_TREE_HEADER_NAME = "devtools.tree.header_name"
DEV_TREE_HEADER_TYPE = "devtools.tree.header_type"
DEV_TREE_HEADER_STATUS = "devtools.tree.header_status"
DEV_TREE_SYNC = "devtools.tree.sync"
DEV_TREE_TYPE_WINDOW = "devtools.tree.type_window"
DEV_TREE_TYPE_CHILD = "devtools.tree.type_child"
DEV_TREE_STATUS_VISIBLE = "devtools.tree.status_visible"
DEV_TREE_STATUS_HIDDEN = "devtools.tree.status_hidden"

DEV_SCENARIO_TITLE = "devtools.scenario.title"
DEV_SCENARIO_RUN = "devtools.scenario.run"
DEV_SCENARIO_STOP = "devtools.scenario.stop"
DEV_SCENARIO_NETWORK = "devtools.scenario.network"
DEV_SCENARIO_UI_STRESS = "devtools.scenario.ui_stress"
DEV_SCENARIO_FIRST_RUN = "devtools.scenario.first_run"
DEV_SCENARIO_MAINTENANCE = "devtools.scenario.maintenance"
DEV_SCENARIO_RESET = "devtools.scenario.reset"

DEV_UI_FPS_LABEL = "devtools.ui.fps_label"
DEV_LOG_INIT = "devtools.log.init"
DEV_LOG_SHOWN = "devtools.log.shown"
DEV_LOG_HIDDEN = "devtools.log.hidden"

DEV_LOG_PROP_SET = "devtools.log.prop_set"
DEV_LOG_PROP_FAIL = "devtools.log.prop_fail"
DEV_LOG_STRESS_APPLIED = "devtools.log.stress_applied"
DEV_LOG_AUTOFILL_DONE = "devtools.log.autofill_done"
