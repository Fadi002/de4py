# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import os
import json
import zipfile
import tempfile
import requests

from de4py.config.config import settings
from de4py.utils.fs import calculate_checksum


class ChecksumMismatchError(Exception):
    pass


def fetch_remote_checksums(version: str) -> dict:
    url = f"{settings.releases_base_url}/{version}/checksums.json"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def verify_zip(zip_path: str, remote_checksums: dict) -> list:
    mismatches = []
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(tmpdir)

        for rel_path, expected_hash in remote_checksums.items():
            full_path = os.path.join(tmpdir, rel_path)
            if not os.path.exists(full_path):
                mismatches.append(f"MISSING: {rel_path}")
                continue
            actual = calculate_checksum(full_path)
            if actual != expected_hash:
                mismatches.append(f"MISMATCH: {rel_path}")

    return mismatches
