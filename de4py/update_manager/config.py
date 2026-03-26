# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Update-specific configuration.

Provides constants and defaults for the update system.
Main user-facing settings (auto_update, update_channel) are
stored in the central de4py.config.config module.
"""

# Default GitHub repository
GITHUB_REPO = "Fadi002/de4py"

# Update channels
CHANNEL_STABLE = "stable"
CHANNEL_BETA = "beta"
CHANNEL_DEV = "dev"
VALID_CHANNELS = (CHANNEL_STABLE, CHANNEL_BETA, CHANNEL_DEV)

# Raw version file URL (fallback)
RAW_VERSION_URL = "https://raw.githubusercontent.com/Fadi002/de4py/main/INFO/version"

# Changelog URL
CHANGELOG_URL = "https://raw.githubusercontent.com/Fadi002/de4py/main/INFO/changelog.json"

# Timeouts (seconds)
API_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 120

# Download chunk size  
DOWNLOAD_CHUNK_SIZE = 8192
