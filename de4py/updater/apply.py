# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import os
import sys
import shutil
import zipfile
import logging
import tempfile
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

INSTALL_ROOT = Path(__file__).parent.parent.parent.absolute()
BACKUP_DIR = Path(os.path.expanduser("~")) / ".de4py" / "backup"

SKIP_ON_UPDATE = {'de4py', 'plugins', 'logs', '__pycache__', '.git'}


def backup_current() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    from de4py.config.config import settings
    backup_path = BACKUP_DIR / f"de4py-{settings.version}-backup.zip"
    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(INSTALL_ROOT):
            dirs[:] = [d for d in dirs if d not in SKIP_ON_UPDATE]
            for file in files:
                fp = Path(root) / file
                zf.write(fp, fp.relative_to(INSTALL_ROOT.parent))

    existing = sorted(BACKUP_DIR.glob("de4py-*-backup.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in existing[3:]:
        old.unlink(missing_ok=True)

    logger.info(f"Backup saved: {backup_path}")
    return backup_path


def apply_update(zip_path: str) -> bool:
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(tmpdir)

            extracted_root = Path(tmpdir)
            candidates = list(extracted_root.iterdir())
            if len(candidates) == 1 and candidates[0].is_dir():
                extracted_root = candidates[0]

            for src in extracted_root.rglob('*'):
                rel = src.relative_to(extracted_root)
                if any(part in SKIP_ON_UPDATE for part in rel.parts):
                    continue
                dest = INSTALL_ROOT / rel
                if src.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)

        return True
    except Exception as e:
        logger.error(f"apply_update failed: {e}")
        return False


def rollback(backup_path: str) -> bool:
    try:
        with zipfile.ZipFile(backup_path, 'r') as zf:
            zf.extractall(INSTALL_ROOT.parent)
        logger.info("Rollback applied.")
        return True
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        return False


def restart_app():
    logger.info("Restarting de4py...")
    subprocess.Popen([sys.executable] + sys.argv)
    sys.exit(0)
