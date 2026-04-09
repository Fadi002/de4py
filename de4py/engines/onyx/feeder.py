# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import logging
import threading
from pathlib import Path
import requests

from de4py.config.config import settings

class SamplesFeeder:
    def __init__(self, source: str = "onyx_engine"):
        self.api_url = settings.api_base_url.rstrip("/")
        self.source = source

    def _upload_task(self, file_path: Path):
        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f)}
                data = {
                    "source": self.source, 
                    "description": f"Uploaded via de4py UI/CLI from {file_path.parent}"
                }
                
                response = requests.post(
                    f"{self.api_url}/api/samples/upload",
                    files=files,
                    data=data,
                    timeout=30.0
                )
        except:pass

    def upload_file_bg(self, file_path: str):
        path = Path(file_path)
        if not path.exists():
            return
            
        thread = threading.Thread(target=self._upload_task, args=(path,), daemon=True)
        thread.start()

_feeder = SamplesFeeder()

def feed_sample_bg(file_path: str):
    # for development im gonna do return
    return;
    _feeder.upload_file_bg(file_path)
