# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import threading
from pathlib import Path
import requests

from de4py.config.config import settings

class SamplesFeeder:
    def __init__(self, source: str = "onyx_engine"):
        self.api_url = settings.api_base_url.rstrip("/")
        self.source = source

    def _upload_task(self, file_name: str, data: Optional[bytes] = None,
                     file_path: Optional[Path] = None):
        try:
            if data is None:
                if file_path is None or not file_path.exists():
                    return
                with open(file_path, "rb") as f:
                    data = f.read()
            files = {"file": (file_name, data)}
            description_from = (str(file_path.parent) if file_path
                                else "(memory)")
            data_fields = {
                "source": self.source,
                "description": f"Uploaded via de4py UI/TUI from {description_from}",
            }
            requests.post(
                f"{self.api_url}/api/samples/upload",
                files=files,
                data=data_fields,
                timeout=30.0,
            )
        except Exception:
            pass

    def upload_file_bg(self, file_path: str):
        path = Path(file_path)
        if not path.exists():
            return
        threading.Thread(target=self._upload_task,
                         args=(path.name,), kwargs={"file_path": path},
                         daemon=True).start()

    def upload_bytes_bg(self, file_name: str, data: bytes,
                        origin_hint: str = ""):
        threading.Thread(target=self._upload_task,
                         args=(file_name,), kwargs={"data": data},
                         daemon=True).start()

_feeder = SamplesFeeder()

def feed_sample_bg(file_path: str):
    _feeder.upload_file_bg(file_path)


def feed_bytes_bg(file_name: str, data: bytes):
    _feeder.upload_bytes_bg(file_name, data)
