# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from .context import context
from .event_bus import bus

class ScenarioEngine:
    @staticmethod
    def trigger_network_blackout():
        bus.log.emit("WARNING", "SCENARIO: Network Blackout")
        context.dev_flags["api_fail"] = True
        bus.api_mode_changed.emit("fail")
        
        if context.main_window:
            try: context.main_window.show_notification("error", "Simulated Connection Failure")
            except: pass

    @staticmethod
    def trigger_ui_stress():
        bus.log.emit("WARNING", "SCENARIO: UI Stress")
        context.dev_flags["anim_speed"] = 5.0
        bus.trigger_ui_stress.emit()

    @staticmethod
    def trigger_first_run():
        bus.log.emit("INFO", "SCENARIO: First Run")
        if context.navigation_manager:
             try: context.navigation_manager._navigate_to("home")
             except: pass

    @staticmethod
    def reset_all():
        bus.log.emit("INFO", "SCENARIO: Reset")
        context.dev_flags = {
            "highlight_mode": False, "inspect_mode": False, "freeze_ui": False,
            "api_fail": False, "api_delay": 0, "api_empty": False, "anim_speed": 1.0
        }
        if context.app:
            context.app.setStyleSheet("")
            bus.api_mode_changed.emit("normal")

    @staticmethod
    def trigger_update_sim():
        bus.log.emit("INFO", "SCENARIO: Update Sim")
        from de4py.updater.check import UpdateCheckResult
        from de4py.ui.widgets.update_dialog import UpdateDialog
        fake = UpdateCheckResult(
            update_available=True,
            local="V3.1.0",
            remote="V9.9.9",
            changelog=[
                {"version": "V9.9.9", "changes": [
                    "Simulated feature A",
                    "Simulated feature B",
                    "Bug fix from devtools sim"
                ]}
            ],
        )
        if context.main_window:
            context._sim_update_dialog = UpdateDialog(fake, parent=context.main_window)
            context._sim_update_dialog.fade_in()
            bus.log.emit("INFO", "Update dialog shown (simulated)")