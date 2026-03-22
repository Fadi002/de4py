# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

LAB_REGISTRY = {}

def register_lab(name, icon=None, category="General"):
    def decorator(cls):
        LAB_REGISTRY[name] = {
            "class": cls,
            "icon": icon,
            "category": category
        }
        return cls
    return decorator

def get_registered_labs():
    return LAB_REGISTRY
