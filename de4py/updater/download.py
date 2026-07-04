# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import os
import re
import requests
from PySide6.QtCore import QThread, Signal

from de4py.config.config import settings

DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), ".de4py", "updates")


def _sanitize_version(version: str) -> str:
    return re.sub(r'[^a-zA-Z0-9._-]', '', version)


class DownloadWorker(QThread):
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, version: str, parent=None):
        super().__init__(parent)
        self.version = version

    def run(self):
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        safe_version = _sanitize_version(self.version).lower()
        filename = f"{safe_version}-stable.zip"
        dest = os.path.join(DOWNLOAD_DIR, filename)
        url = f"https://github.com/Fadi002/de4py/archive/refs/tags/{safe_version}-stable.zip"

        try:
            r = requests.get(url, stream=True, timeout=30)
            r.raise_for_status()
            total = int(r.headers.get('content-length', 0))
            downloaded = 0

            tmp_dest = dest + ".part"
            try:
                with open(tmp_dest, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=262144):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                self.progress.emit(int(downloaded / total * 100))

                os.replace(tmp_dest, dest)
                self.finished.emit(dest)
            except Exception:
                if os.path.exists(tmp_dest):
                    os.remove(tmp_dest)
                raise

        except requests.ConnectionError:
            self.error.emit("Connection lost during download.")
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "unknown"
            self.error.emit(f"Download failed: HTTP {status}")
        except Exception as e:
            self.error.emit(f"Download error: {e}")
